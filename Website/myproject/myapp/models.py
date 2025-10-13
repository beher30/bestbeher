from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
import uuid
import os
import logging
from django.db import transaction
from PIL import Image
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from .services.mega_service import MegaService
import ffmpeg_streaming
from ffmpeg_streaming import Formats, Representation, Size
import tempfile
import requests
import subprocess
from urllib.parse import urlparse
from django.core.files import File
from .services.mega_thumbnail_service import generate_video_thumbnail

logger = logging.getLogger(__name__)

def validate_file_size(value):
    filesize = value.size
    if filesize > 2 * 1024 * 1024:  # 2MB
        raise ValidationError("Maximum file size is 2MB")

def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1]
    valid_extensions = ['.jpg', '.jpeg', '.png']
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension. Please use JPG, JPEG, or PNG')

def validate_payment_proof(value):
    # Check file size (2MB limit)
    if value.size > 2 * 1024 * 1024:
        raise ValidationError('File size must be under 2MB')
    
    # Check file type
    valid_extensions = ['.jpg', '.jpeg', '.png']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError('Only JPG, JPEG, and PNG files are allowed')

class UserProfile(models.Model):
    MEMBERSHIP_CHOICES = [
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('diamond', 'Diamond')
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    membership_tier = models.CharField(max_length=10, choices=MEMBERSHIP_CHOICES, default='regular')
    membership_start_date = models.DateTimeField(null=True, blank=True)
    membership_end_date = models.DateTimeField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    profile_picture_thumbnail = models.ImageField(upload_to='profile_pictures/thumbnails/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        if self.profile_picture and not self.profile_picture_thumbnail:
            # Generate thumbnail
            try:
                from PIL import Image
                from io import BytesIO
                from django.core.files.base import ContentFile
                import os

                # Open the uploaded image
                image = Image.open(self.profile_picture)
                
                # Convert to RGB if necessary
                if image.mode not in ('L', 'RGB'):
                    image = image.convert('RGB')
                
                # Create thumbnail
                image.thumbnail((100, 100), Image.Resampling.LANCZOS)
                
                # Save thumbnail to in-memory file
                thumb_io = BytesIO()
                image.save(thumb_io, format='JPEG', quality=85)
                thumb_io.seek(0)

                # Generate thumbnail filename
                thumb_filename = os.path.splitext(self.profile_picture.name)[0] + '_thumb.jpg'
                
                # Save thumbnail to storage and set model field
                self.profile_picture_thumbnail.save(
                    thumb_filename,
                    ContentFile(thumb_io.getvalue()),
                    save=False
                )
            except Exception as e:
                logger.error(f"Error creating thumbnail for {self.user.username}: {str(e)}")

        super().save(*args, **kwargs)

    def get_membership_tier_display(self):
        return dict(self.MEMBERSHIP_CHOICES).get(self.membership_tier, 'Regular')

    def is_membership_active(self):
        if not self.membership_end_date:
            return False
        return timezone.now() <= self.membership_end_date

    def get_accessible_videos(self):
        """Returns videos accessible to the user based on membership tier"""
        if not self.is_membership_active():
            return Video.objects.filter(membership_tier='regular', is_active=True)
            
        if self.membership_tier == 'diamond':
            return Video.objects.filter(is_active=True)
            
        if self.membership_tier == 'vip':
            return Video.objects.filter(
                models.Q(membership_tier='regular') | 
                models.Q(membership_tier='vip'),
                is_active=True
            )
            
        # Regular members
        return Video.objects.filter(membership_tier='regular', is_active=True)

    def can_access_video(self, video):
        """Check if user can access a specific video"""
        if not self.is_membership_active() and video.membership_tier != 'regular':
            return False
            
        if self.membership_tier == 'diamond':
            return True
            
        if self.membership_tier == 'vip':
            return video.membership_tier in ['regular', 'vip']
            
        # Regular members
        return video.membership_tier == 'regular'

    def get_completed_videos(self):
        """Get videos that the user has completed"""
        return Video.objects.filter(
            progress__user=self.user,
            progress__completed=True
        )

    def get_in_progress_videos(self):
        """Get videos that the user has started but not completed"""
        return Video.objects.filter(
            progress__user=self.user,
            progress__completed=False,
            progress__progress__gt=0
        )

    def get_next_video(self, current_video):
        """Get the next video in sequence that the user can access"""
        accessible_videos = self.get_accessible_videos()
        try:
            return accessible_videos.filter(
                upload_date__gt=current_video.upload_date
            ).order_by('upload_date').first()
        except:
            return None

    def get_previous_video(self, current_video):
        """Get the previous video in sequence that the user can access"""
        accessible_videos = self.get_accessible_videos()
        try:
            return accessible_videos.filter(
                upload_date__lt=current_video.upload_date
            ).order_by('-upload_date').first()
        except:
            return None


class MembershipTier(models.Model):
    MEMBERSHIP_TIERS = [
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('diamond', 'Diamond')
    ]
    
    name = models.CharField(max_length=255)
    tier = models.CharField(
        max_length=10,
        choices=MEMBERSHIP_TIERS,
        default='regular'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Video(models.Model):
    is_free = models.BooleanField(default=False, help_text='Mark as free video for public viewing')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    url = models.URLField(help_text='Video streaming URL', unique=True)
    mega_link = models.URLField(max_length=500, help_text='MEGA video link', blank=True)
    duration = models.DurationField(null=True, blank=True)
    duration_ms = models.BigIntegerField(null=True, blank=True)  # Duration in milliseconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0)
    tier = models.ForeignKey('MembershipTier', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    
    # Security and playback settings
    is_streaming_enabled = models.BooleanField(default=True)
    watermark_enabled = models.BooleanField(default=True)
    prevent_download = models.BooleanField(default=True)
    analytics_enabled = models.BooleanField(default=True)
    secure_playback = models.BooleanField(default=True, help_text='Enable token-based secure playback')
    
    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['order', 'created_at']
        
    def get_membership_tier_display(self):
        if self.is_free:
            return 'Free'
        return self.tier.name if self.tier else 'Free'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
    def is_accessible_to_user(self, user):
        """Check if video is accessible to a specific user"""
        if not user.is_authenticated:
            return False
        
        try:
            profile = user.profile
            return profile.can_access_video(self)
        except:
            return False
    
    def get_user_progress(self, user):
        """Get user's progress for this video"""
        if not user.is_authenticated:
            return None
        
        try:
            return self.progress.get(user=user)
        except VideoProgress.DoesNotExist:
            return None
    
    def increment_view_count(self):
        """Increment view count for this video"""
        self.views += 1
        self.save(update_fields=['views'])
    
    def get_next_video(self, user):
        """Get next video in sequence that is accessible to user"""
        try:
            profile = user.profile
            next_video = Video.objects.filter(
                order__gt=self.order,
                is_active=True
            ).order_by('order').first()
            
            if next_video and profile.can_access_video(next_video):
                return next_video
            return None
        except:
            return None
    
    def get_previous_video(self, user):
        """Get previous video in sequence that is accessible to user"""
        try:
            profile = user.profile
            prev_video = Video.objects.filter(
                order__lt=self.order,
                is_active=True
            ).order_by('-order').first()
            
            if prev_video and profile.can_access_video(prev_video):
                return prev_video
            return None
        except:
            return None

    def get_stream_session(self, user):
        """Get or create a valid streaming session for the user"""
        session = self.stream_sessions.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if not session and self.is_streaming_enabled:
        
        
        
            if drive_video:
                session = VideoStreamSession.objects.create(
                    user=user,
                    video=self,
                    drive_video=drive_video,
                
                    expires_at=timezone.now() + timezone.timedelta(hours=1),
                    watermark_data={
                        'user_id': user.id,
                        'email': user.email,
                        'timestamp': timezone.now().isoformat()
                    }
                )
        
        return session

    def track_analytics(self, session, event_type, position, duration, metadata=None):
        """Track video analytics events"""
        if self.analytics_enabled and session:
            VideoAnalytics.objects.create(
                session=session,
                event_type=event_type,
                position=position,
                duration=duration,
                metadata=metadata or {}
            )

    def get_stream_url(self, user=None):
        """Get the streaming URL for the video"""
        try:
            from .services.mega_service import MegaService
            
            # If we have a MEGA link and user is provided, generate a secure URL
            if user and self.mega_link and self.secure_playback:
                mega_service = MegaService()
                return mega_service.get_video_embed_url(self.mega_link, user)
            
            # Fallback to regular URL if no MEGA link or no secure playback
            return self.url
        except Exception as e:
            logger.error(f"Error getting stream URL for video {self.id}: {str(e)}")
            return self.url

class Course(models.Model):
    """Model for organizing videos into courses"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='course_thumbnails/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Order in which courses should be displayed")
    
    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['order', 'created_at']
        
    def get_first_video(self):
        """Returns the first video in the course"""
        return self.videos.filter(is_active=True).order_by('order', 'upload_date').first()
    
    def get_videos_by_tier(self, tier):
        """Returns videos accessible to a specific membership tier"""
        if tier == 'diamond':
            return self.videos.filter(is_active=True)
        elif tier == 'vip':
            return self.videos.filter(
                models.Q(membership_tier='regular') | 
                models.Q(membership_tier='vip'),
                is_active=True
            )
        else:
            return self.videos.filter(membership_tier='regular', is_active=True)



class PaymentProof(models.Model):
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    )
    
    MEMBERSHIP_TIERS = (
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('diamond', 'Diamond')
    )
    
    TIER_PRICING = {
        'regular': 0,    # Free
        'vip': 25,      # $25/month
        'diamond': 50    # $50/month
    }
    
    TIER_DURATION = {
        'regular': 0,    # No duration for regular
        'vip': 90,      # 3 months
        'diamond': 365   # 1 year
    }
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_proofs')
    image = models.ImageField(upload_to='payment_proofs/', validators=[validate_payment_proof])
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    requested_tier = models.CharField(max_length=10, choices=MEMBERSHIP_TIERS, default='regular')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_proofs')
    processed_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']
        
    def __str__(self):
        return f"{self.user.username}'s payment proof - {self.get_status_display()}"
        
    def get_status_badge_class(self):
        return {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger'
        }.get(self.status, 'secondary')
        
    def clean(self):
        if self.status in ['approved', 'rejected'] and not self.processed_by:
            raise ValidationError('Processed payment proofs must have a processor')
        if self.status in ['approved', 'rejected'] and not self.processed_at:
            raise ValidationError('Processed payment proofs must have a processing time')
            
    def save(self, *args, **kwargs):
        if self.status in ['approved', 'rejected'] and not self.processed_at:
            self.processed_at = timezone.now()
        super().save(*args, **kwargs)

    def get_amount(self):
        """Get the amount for this payment based on the requested tier."""
        return self.TIER_PRICING.get(self.requested_tier, 0)
    
    def get_duration(self):
        """Get the membership duration in days based on the requested tier."""
        return self.TIER_DURATION.get(self.requested_tier, 30)
    
    def approve(self, admin_user, feedback=None):
        self.status = 'approved'
        self.processed_at = timezone.now()
        self.processed_by = admin_user
        self.feedback = feedback
        self.save()
        
        # Update user's membership
        profile = self.user.profile
        profile.membership_tier = self.requested_tier
        profile.membership_start_date = timezone.now()
        profile.membership_end_date = timezone.now() + timezone.timedelta(days=self.get_duration())
        profile.save()
        
        # Log the activity
        AuditLog.objects.create(
            user=self.user,
            action_type='payment',
            action=f'Payment proof approved for {self.requested_tier} membership (${self.get_amount()}) by {admin_user.username}',
            ip_address=None,  # Will be set by the view
            status='success',
            related_user=admin_user
        )
        
        # Log membership change
        AuditLog.objects.create(
            user=self.user,
            action_type='membership_change',
            action=f'Membership upgraded to {self.requested_tier} tier for {self.get_duration()} days',
            ip_address=None,  # Will be set by the view
            status='success',
            related_user=admin_user
        )
    
    def reject(self, admin_user, feedback=None):
        self.status = 'rejected'
        self.processed_at = timezone.now()
        self.processed_by = admin_user
        self.feedback = feedback
        self.save()
        
        # Log the activity
        AuditLog.objects.create(
            user=self.user,
            action_type='payment',
            action=f'Payment proof rejected for {self.requested_tier} membership (${self.get_amount()}) by {admin_user.username}. Reason: {feedback or "No reason provided"}',
            ip_address=None,  # Will be set by the view
            status='rejected',
            related_user=admin_user
        )

class AuditLog(models.Model):
    ACTION_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('register', 'Register'),
        ('profile_update', 'Profile Update'),
        ('payment', 'Payment'),
        ('video_upload', 'Video Upload'),
        ('video_delete', 'Video Delete'),
        ('membership_change', 'Membership Change'),
        ('settings_update', 'Settings Update'),
        ('user_activation', 'User Activation'),
        ('user_deactivation', 'User Deactivation')
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # If user is deleted, keep the audit log
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    action = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=20, default='success')
    related_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_audit_logs'
    )
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        username = self.user.username if self.user else 'Anonymous'
        return f"{username} - {self.action_type} - {self.timestamp}"

class MegaVideo(models.Model):
    """Model for videos hosted on MEGA, pCloud, or Google Drive"""
    is_free = models.BooleanField(default=False, help_text='Mark as free video for public viewing')
    
    MEMBERSHIP_TIERS = [
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('diamond', 'Diamond'),
    ]
    
    VIDEO_SOURCES = [
        ('mega', 'MEGA'),
        ('pcloud', 'pCloud'),
        ('gdrive', 'Google Drive'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_source = models.CharField(
        max_length=20, 
        choices=VIDEO_SOURCES, 
        default='mega',
        help_text='Video hosting platform'
    )
    mega_file_link = models.URLField(max_length=500, help_text='Video link (MEGA/pCloud/Google Drive)')
    thumbnail = models.ImageField(
        upload_to='mega_video_thumbnails/',
        null=True,
        blank=True,
        validators=[validate_file_size, validate_file_extension],
        help_text='Video thumbnail image (max 2MB, JPG/PNG)'
    )
    thumbnail_url = models.URLField(max_length=500, blank=True)
    membership_tier = models.CharField(max_length=20, choices=MEMBERSHIP_TIERS, default='regular')
    duration_ms = models.BigIntegerField(null=True, blank=True)
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def duration(self):
        """Return formatted duration string"""
        if self.duration_ms:
            seconds = self.duration_ms / 1000
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}:{remaining_seconds:02d}"
        return "Unknown"

    def get_stream_url(self, user):
        """Get secure streaming URL for this video"""
        if not user.is_authenticated:
            return None
        
        # Check if user has access to this tier
        if user.is_staff or user.is_superuser:
            return self.mega_file_link
            
        user_tier = user.profile.membership_tier.lower()
        video_tier = self.membership_tier.lower()
        
        tier_levels = {
            'regular': 0,
            'vip': 1,
            'diamond': 2
        }
        
        if tier_levels.get(user_tier, -1) >= tier_levels.get(video_tier, 0):
            return self.mega_file_link
            
        return None

    def get_absolute_url(self):
        """Get URL for viewing this video"""
        return reverse('video_player', kwargs={'video_id': self.id})

    def save(self, *args, **kwargs):
        # If no thumbnail is provided and we have a MEGA link, try to generate one
        if not self.thumbnail and not self.thumbnail_url and self.mega_file_link:
            try:
                # Generate thumbnail from video
                thumbnail_path = generate_video_thumbnail(self.mega_file_link)
                
                if thumbnail_path:
                    # Save the generated thumbnail
                    with open(thumbnail_path, 'rb') as f:
                        self.thumbnail.save(
                            f"video_{uuid.uuid4()}.jpg",
                            File(f),
                            save=False
                        )
            except Exception as e:
                logger.error(f"Error generating thumbnail: {str(e)}")

        # If a new thumbnail is uploaded, update the thumbnail URL
        if self.thumbnail and not self.thumbnail_url:
            self.thumbnail_url = self.thumbnail.url

        super().save(*args, **kwargs)

    def get_thumbnail_url(self):
        """Get the thumbnail URL, with fallback to a default image"""
        if self.thumbnail:
            return self.thumbnail.url
        elif self.thumbnail_url:
            return self.thumbnail_url
        return '/static/img/default-thumbnail.jpg'

class MembershipAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tier = models.ForeignKey(MembershipTier, on_delete=models.CASCADE, null=True, blank=True)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_access')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = 'Membership Access'


class AccessRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tier = models.ForeignKey(MembershipTier, on_delete=models.CASCADE, null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='processed_requests')
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.tier.name} - {self.status}"


class VideoContent(models.Model):
    """Alternative video model for content management"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tier = models.ForeignKey(MembershipTier, on_delete=models.CASCADE, null=True, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    duration_ms = models.BigIntegerField(null=True, blank=True)  # Store duration in milliseconds
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def duration(self):
        """Return formatted duration string"""
        if not self.duration_ms:
            return "Unknown"
        
        total_seconds = int(self.duration_ms / 1000)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


class VideoProgress(models.Model):
    """Model to track user progress on videos"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_progress')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='progress')
    progress = models.FloatField(default=0, help_text='Progress percentage (0-100)')
    current_time = models.FloatField(default=0, help_text='Current time in seconds')
    completed = models.BooleanField(default=False)
    last_watched = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_watched']
        unique_together = ('user', 'video')
    
    def __str__(self):
        return f"{self.user.username} - {self.video.title} - {self.progress:.1f}%"
    
    def update_progress(self, current_time, duration):
        """Update progress based on current time and duration"""
        if duration > 0:
            self.progress = min(100, (current_time / duration) * 100)
            if self.progress >= 95:
                self.completed = True
        self.current_time = current_time
        self.save()


class VideoStreamSession(models.Model):
    """Model to manage video streaming sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stream_sessions')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='stream_sessions')

    signed_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    last_position = models.FloatField(default=0)
    watermark_data = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.user.username} - {self.video.title}"

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        """Check if the session is still valid"""
        return self.is_active and timezone.now() <= self.expires_at

class VideoAnalytics(models.Model):
    """Model to track video analytics"""
    session = models.ForeignKey(VideoStreamSession, on_delete=models.CASCADE, related_name='analytics')
    event_type = models.CharField(max_length=50)  # play, pause, seek, complete
    timestamp = models.DateTimeField(auto_now_add=True)
    position = models.FloatField()
    duration = models.FloatField()
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ['timestamp']

class MembershipUpgradeRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='upgrade_requests')
    desired_tier = models.CharField(max_length=10, choices=UserProfile.MEMBERSHIP_CHOICES)
    reason = models.TextField()
    screenshot = models.ImageField(upload_to='upgrade_proofs/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='processed_upgrades'
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Membership Upgrade Request'
        verbose_name_plural = 'Membership Upgrade Requests'

    def __str__(self):
        return f"{self.user.username} - {self.get_desired_tier_display()} ({self.status})"

    def get_desired_tier_display(self):
        return dict(UserProfile.MEMBERSHIP_CHOICES).get(self.desired_tier, self.desired_tier)

    def approve(self, admin_user, comment=''):
        """Approve the upgrade request"""
        with transaction.atomic():
            self.status = 'approved'
            self.admin_comment = comment
            self.processed_by = admin_user
            self.processed_at = timezone.now()
            self.save()

            # Update user's profile
            profile = self.user.profile
            profile.membership_tier = self.desired_tier
            profile.membership_start_date = timezone.now()
            profile.membership_end_date = timezone.now() + timezone.timedelta(days=365)
            profile.save()

            # Log the change
            AuditLog.objects.create(
                user=admin_user,
                action_type='membership_change',
                action=f'Approved upgrade request to {self.get_desired_tier_display()}',
                ip_address=None,  # Will be set in the view
                status='success',
                related_user=self.user
            )

    def reject(self, admin_user, comment=''):
        """Reject the upgrade request"""
        self.status = 'rejected'
        self.admin_comment = comment
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save()

        # Log the rejection
        AuditLog.objects.create(
            user=admin_user,
            action_type='membership_change',
            action=f'Rejected upgrade request to {self.get_desired_tier_display()}',
            ip_address=None,  # Will be set in the view
            status='rejected',
            related_user=self.user
        )
