from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import (
    PaymentProof, UserProfile, Video, AuditLog,
    MembershipTier, MembershipAccess, AccessRequest,
    VideoStreamSession, VideoAnalytics, MegaVideo,
    MembershipUpgradeRequest
)
from django.utils.html import mark_safe, format_html
from django.utils import timezone
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.core.mail import send_mail
from datetime import timedelta
from django.conf import settings

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_membership_tier')
    
    def get_membership_tier(self, obj):
        return obj.profile.get_membership_tier_display()
    get_membership_tier.short_description = 'Membership'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    list_display = ('user', 'requested_tier', 'status', 'uploaded_at', 'processed_at', 'processed_by')
    list_filter = ('status', 'requested_tier', 'processed_at')
    search_fields = ('user__username', 'user__email', 'admin_feedback')
    readonly_fields = ('uploaded_at', 'processed_at', 'processed_by')
    
    def payment_proof_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return "No image"
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('user', 'image', 'requested_tier', 'status')
        }),
        ('Processing Details', {
            'fields': ('admin_feedback', 'processed_at', 'processed_by')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'approved':
                obj.approve(request.user, obj.admin_feedback)
            elif obj.status == 'rejected':
                obj.reject(request.user, obj.admin_feedback)
        else:
            super().save_model(request, obj, form, change)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'membership_tier', 'membership_start_date', 'membership_end_date', 'profile_picture_display')
    list_filter = ('membership_tier',)
    search_fields = ('user__username',)
    readonly_fields = ('membership_start_date',)

    def profile_picture_display(self, obj):
        if obj.profile_picture:
            return mark_safe(f'<img src="{obj.profile_picture.url}" style="width: 50px; height: 50px;" />')
        return "No Image"
    profile_picture_display.short_description = 'Profile Picture'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['membership_tier'].widget.attrs['style'] = 'width: 200px;'
        return form


class MembershipTierAdmin(admin.ModelAdmin):
    list_display = ['name', 'tier', 'is_active', 'created_at']
    list_filter = ['tier', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

class MembershipAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'granted_by', 'granted_at', 'expires_at', 'is_active']
    list_filter = ['tier', 'is_active', 'granted_at']
    search_fields = ['user__username', 'tier__name']
    readonly_fields = ['granted_at']

class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'requested_at', 'status', 'processed_by']
    list_filter = ['tier', 'status', 'requested_at']
    search_fields = ['user__username', 'tier__name']
    readonly_fields = ['requested_at', 'processed_at']

class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'tier', 'created_at', 'duration', 'is_free']
    list_filter = ['tier', 'is_free', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'views']
    actions = ['delete_selected']
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def delete_model(self, request, obj):
        # Log the deletion
        AuditLog.objects.create(
            user=request.user,
            action_type='video_delete',
            action=f'Deleted video: {obj.title}',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        # Delete the video
        obj.delete()

    def delete_queryset(self, request, queryset):
        # Log bulk deletions
        for obj in queryset:
            AuditLog.objects.create(
                user=request.user,
                action_type='video_delete',
                action=f'Deleted video: {obj.title} (bulk delete)',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        # Delete the videos
        queryset.delete()

class VideoStreamSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'video', 'created_at', 'expires_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'video__title']
    readonly_fields = ['id', 'created_at']

class VideoAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['session', 'event_type', 'timestamp', 'position']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['session__user__username', 'session__video__title']
    readonly_fields = ['timestamp']

class MegaVideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'membership_tier', 'is_free', 'created_at', 'views', 'thumbnail_preview']
    list_filter = ['membership_tier', 'is_free', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'views', 'thumbnail_preview']
    fieldsets = (
        ('Video Information', {
            'fields': ('title', 'description', 'mega_file_link', 'is_free', 'membership_tier')
        }),
        ('Thumbnail', {
            'fields': ('thumbnail', 'thumbnail_url', 'thumbnail_preview')
        }),
        ('Statistics', {
            'fields': ('views', 'duration_ms', 'created_at', 'updated_at')
        }),
    )
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" width="100" height="auto" />', obj.thumbnail.url)
        elif obj.thumbnail_url:
            return format_html('<img src="{}" width="100" height="auto" />', obj.thumbnail_url)
        return "No thumbnail"
    thumbnail_preview.short_description = 'Thumbnail Preview'
    
    def save_model(self, request, obj, form, change):
        # Log the action
        action_type = 'mega_video_update' if change else 'mega_video_create'
        action_desc = f'Updated mega video: {obj.title}' if change else f'Created mega video: {obj.title}'
        
        AuditLog.objects.create(
            user=request.user,
            action_type=action_type,
            action=action_desc,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        super().save_model(request, obj, form, change)
    
    def delete_model(self, request, obj):
        # Log the deletion
        AuditLog.objects.create(
            user=request.user,
            action_type='mega_video_delete',
            action=f'Deleted mega video: {obj.title}',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        # Delete the video
        obj.delete()

# Register your models here
admin.site.register(MembershipTier, MembershipTierAdmin)
admin.site.register(MembershipAccess, MembershipAccessAdmin)
admin.site.register(AccessRequest, AccessRequestAdmin)
admin.site.register(Video, VideoAdmin)
admin.site.register(VideoStreamSession, VideoStreamSessionAdmin)
admin.site.register(VideoAnalytics, VideoAnalyticsAdmin)
admin.site.register(MegaVideo, MegaVideoAdmin)

@admin.register(MembershipUpgradeRequest)
class MembershipUpgradeRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'desired_tier', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'desired_tier', 'created_at')
    search_fields = ('user__username', 'user__email', 'reason')
    readonly_fields = ('created_at', 'updated_at', 'processed_at', 'processed_by')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'desired_tier')
        }),
        ('Request Details', {
            'fields': ('reason', 'screenshot')
        }),
        ('Status Information', {
            'fields': ('status', 'admin_comment')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at', 'processed_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            obj.processed_by = request.user
            obj.processed_at = timezone.now()
            
            if obj.status == 'approved':
                # Update user's membership
                profile = obj.user.userprofile
                profile.membership_tier = obj.desired_tier
                profile.membership_start_date = timezone.now()
                profile.membership_end_date = timezone.now() + timedelta(days=30)  # 30-day membership
                profile.save()
                
                # Send email notification to user
                subject = 'Membership Upgrade Approved'
                message = f"""
                Dear {obj.user.username},
                
                Your request to upgrade to {obj.get_desired_tier_display()} membership has been approved.
                Your new membership is now active and will expire on {profile.membership_end_date.strftime('%B %d, %Y')}.
                
                Thank you for your continued support!
                """
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [obj.user.email],
                    fail_silently=False,
                )
            elif obj.status == 'rejected':
                # Send email notification to user
                subject = 'Membership Upgrade Request Status'
                message = f"""
                Dear {obj.user.username},
                
                Your request to upgrade to {obj.get_desired_tier_display()} membership has been rejected.
                
                Reason: {obj.admin_comment or 'No reason provided'}
                
                If you have any questions, please contact our support team.
                """
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [obj.user.email],
                    fail_silently=False,
                )
        
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        return False  # Prevent deletion of upgrade requests
