# myapp/views.py
import os
import json
import time
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm, PaymentProofForm, MembershipUpgradeRequestForm
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, StreamingHttpResponse, HttpResponseForbidden
from django.db.models import Prefetch, Count, Sum, Value
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from .models import UserProfile, PaymentProof, AuditLog, Video, Course, VideoProgress, VideoStreamSession, VideoAnalytics, AccessRequest, MembershipAccess, MegaVideo, MembershipUpgradeRequest
import logging
logger = logging.getLogger(__name__)

def is_admin(user):
    # Allow superusers and staff members
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def index(request):
    """Landing page view"""
    try:
        profile = None
        if request.user.is_authenticated:
            profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'membership_tier': 'regular'}
            )
        
        context = {
            'user': request.user,
            'profile': profile
        }
        
        return render(request, 'index.html', context)
        
    except Exception as e:
        logger.error(f"Error in index view: {str(e)}")
        messages.error(request, "An error occurred. Please try again later.")
        return redirect('welcome')

@login_required
def welcome_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        # Get all available videos
        all_videos = get_all_video_paths()
        
        # Get user's profile, create if doesn't exist
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'membership_tier': 'none'}
        )
        
        # Get accessible and locked videos based on membership
        accessible_videos, locked_videos = profile.get_accessible_videos(all_videos)
        
        context = {
            'membership_tier': profile.get_membership_tier_display(),
            'membership_end_date': profile.membership_end_date,
            'is_vip': profile.membership_tier == 'vip',
            'accessible_videos': accessible_videos,
            'locked_videos': locked_videos,
        }
        
        return render(request, 'video_streaming/01. Welcome!.html', context)
    except Exception as e:
        logger.error(f"Error in welcome_view: {str(e)}")
        messages.error(request, "An error occurred while loading your videos. Please try again later.")
        return redirect('index')

@login_required
def video_view(request, video_name):
    try:
        # Validate video exists
        video_path = f"{video_name}.html"
        all_videos = get_all_video_paths()
        
        if video_path not in [video['path'] for video in all_videos]:
            messages.error(request, "Video not found.")
            return redirect('welcome')
            
        # Check user's access
        profile = request.user.profile
        accessible_videos, _ = profile.get_accessible_videos(all_videos)
        
        if video_path not in accessible_videos:
            if profile.membership_tier == 'none':
                messages.warning(request, "Please upgrade your membership to access this video.")
                return redirect('payment_required')
            elif profile.membership_tier == 'vip':
                messages.warning(request, "This video requires Diamond membership. Please upgrade to access it.")
                return redirect('payment_required')
            else:
                messages.error(request, "You don't have access to this video.")
                return redirect('welcome')
        
        return render(request, f'video_streaming/{video_path}')
    except Exception as e:
        logger.error(f"Error in video_view: {str(e)}")
        messages.error(request, "An error occurred while loading the video. Please try again later.")
        return redirect('welcome')

def payment_required(request):
    return render(request, 'payment_required.html')

def terms_and_conditions(request):
    return render(request, 'terms-and-conditions.html')

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(user=user)
            # Make the first user a staff member
            if User.objects.count() == 1:
                user.is_staff = True
                user.is_active = True
                user.save()
            login(request, user)
            return redirect('index')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    # Get client IP for audit logging
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0]
    else:
        ip_address = request.META.get('REMOTE_ADDR')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Log the successful login
                AuditLog.objects.create(
                    user=user,
                    action_type='login',
                    action=f'User {username} logged in successfully',
                    ip_address=ip_address,
                    status='success'
                )
                
                if user.is_staff or user.is_superuser:
                    return redirect('admin_dashboard')
                return redirect('index')
        
        # Log failed login attempt (either invalid form or failed authentication)
        username = request.POST.get('username', '')
        AuditLog.objects.create(
            user=None,  # No user since login failed
            action_type='login',
            action=f'Failed login attempt for username: {username}',
            ip_address=ip_address,
            status='failed'
        )
        
        # Add a generic error message for security
        form.add_error(None, 'Invalid username or password')
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {
        'form': form,
        'page_title': 'Login',
        'submit_text': 'Sign In'
    })

def logout_view(request):
    if request.user.is_authenticated:
        username = request.user.username
        user = request.user
        
        # Get client IP for audit logging
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        # Log the logout
        AuditLog.objects.create(
            user=user,
            action_type='logout',
            action=f'User {username} logged out',
            ip_address=ip_address,
            status='success'
        )
        
        logout(request)
    return redirect('index')

@login_required
def home(request):
    return render(request, 'base.html')

@login_required
def courses_view(request):
    """View for displaying available courses based on membership."""
    user_profile = request.user.profile
    accessible_videos = user_profile.get_accessible_videos()
    
    context = {
        'videos': accessible_videos,
        'membership_tier': user_profile.get_membership_tier_display(),
        'is_active_member': user_profile.has_active_membership(),
        'membership_expiry': user_profile.membership_end_date,
    }
    return render(request, 'courses.html', context)

@login_required
def admin_dashboard(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")

    # Get all videos
    videos = Video.objects.all().order_by('-created_at')
    
    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        videos = videos.filter(title__icontains=search_query)
    
    # Handle tier filter
    tier_filter = request.GET.get('tier', '')
    if tier_filter:
        videos = videos.filter(tier__tier=tier_filter)
    
    # Pagination
    paginator = Paginator(videos, 9)  # Show 9 videos per page
    page_number = request.GET.get('page', 1)
    videos_page = paginator.get_page(page_number)
    
    # Get membership stats
    membership_stats = MembershipAccess.objects.filter(is_active=True).values('tier__tier').annotate(
        count=Count('id')
    ).order_by('tier__tier')
    
    # Get video stats
    video_stats = Video.objects.values('tier__tier').annotate(
        count=Count('id'),
        total_views=Sum('views')
    ).order_by('tier__tier')
    
    # Get MEGA video counts
    from .models import MegaVideo
    mega_video_counts = {
        'total': MegaVideo.objects.count(),
        'regular': MegaVideo.objects.filter(membership_tier='regular').count(),
        'vip': MegaVideo.objects.filter(membership_tier='vip').count(),
        'diamond': MegaVideo.objects.filter(membership_tier='diamond').count()
    }
    
    context = {
        'videos': videos_page,
        'search_query': search_query,
        'tier_filter': tier_filter,
        'membership_stats': membership_stats,
        'video_stats': video_stats,
        'mega_video_counts': mega_video_counts,
    }
    
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
def user_details(request, user_id):
    if not request.user.is_staff:
        return redirect('dashboard')
    user = get_object_or_404(User, id=user_id)
    return render(request, 'dashboard/user_details.html', {'user': user})

@login_required
def verify_payment(request, proof_id, action):
    if not is_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Permission denied'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    proof = get_object_or_404(PaymentProof.objects.select_related('user'), id=proof_id)
    
    if action not in ['approve', 'reject']:
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    
    feedback = request.POST.get('feedback', '')
    membership_tier = request.POST.get('membership_tier', 'vip')  # Default to VIP if not specified
    
    try:
        with transaction.atomic():
            proof.status = 'approved' if action == 'approve' else 'rejected'
            proof.admin_feedback = feedback
            proof.reviewed_at = timezone.now()
            proof.reviewed_by = request.user
            proof.save()
            
            # If approved, activate the user's account and set membership
            if action == 'approve':
                user = proof.user
                user.is_active = True
                user.save()
                
                # Get or create user profile
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'membership_tier': 'none'}
                )
                
                # Update user's profile with membership information
                profile.membership_tier = membership_tier
                profile.membership_start_date = timezone.now()
                profile.membership_end_date = timezone.now() + timezone.timedelta(days=365)
                profile.save()
                
                # Clear cache
                try:
                    cache.delete(f'user_videos_{user.id}')
                    logger.info(f"Cleared cache for user {user.id}")
                except Exception as cache_error:
                    logger.warning(f"Failed to clear cache: {str(cache_error)}")
                
        return JsonResponse({
            'success': True,
            'message': f'Payment proof {action}d successfully',
            'status': proof.status,
            'reviewed_at': proof.reviewed_at.strftime('%Y-%m-%d %H:%M:%S'),
            'reviewed_by': proof.reviewed_by.username,
            'membership_tier': profile.get_membership_tier_display()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error processing payment: {str(e)}'
        })

@login_required
def activate_user(request, user_id):
    if not is_admin(request.user):
        return JsonResponse({
            'success': False,
            'message': "You don't have permission to activate users."
        }, status=403)
    
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        }, status=405)
    
    try:
        with transaction.atomic():
            user = get_object_or_404(User.objects.select_related('profile'), id=user_id)
            
            if user.is_superuser:
                return JsonResponse({
                    'success': False,
                    'message': 'Cannot modify superuser status'
                }, status=400)
            
            # Activate the user
            user.is_active = True
            user.save()
            
            # Ensure user has a profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # If no membership is set, set to default 'none'
            if not profile.membership_tier:
                profile.membership_tier = 'none'
                profile.save()
            
            # Clear cache
            try:
                cache.delete(f'user_videos_{user.id}')
                logger.info(f"Cleared cache for user {user.id}")
            except Exception as cache_error:
                logger.warning(f"Failed to clear cache: {str(cache_error)}")
            
            return JsonResponse({
                'success': True,
                'message': 'User activated successfully'
            })
            
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'User not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error activating user: {str(e)}'
        }, status=500)

@login_required
def deactivate_user(request, user_id):
    if not is_admin(request.user):
        return JsonResponse({
            'success': False,
            'message': "You don't have permission to deactivate users."
        })
    
    try:
        user = get_object_or_404(User, id=user_id)
        if not user.is_superuser:
            user.is_active = False
            user.save()
            return JsonResponse({
                'success': True,
                'message': f'User {user.username} has been deactivated successfully.'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Cannot deactivate superuser accounts.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
def update_membership(request, user_id):
    """Update user's membership tier"""
    # Only allow staff or superuser
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({
            'success': False,
            'message': "You don't have permission to perform this action."
        }, status=403)
    try:
        # First try to get data from POST
        new_tier = request.POST.get('membership_tier')
        
        # If not in POST, try to parse from JSON body
        if not new_tier and request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
                new_tier = data.get('membership_tier')
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': f'Invalid JSON data: {str(e)}'
                }, status=400)
        
        # Validate the tier value
        if not new_tier or new_tier not in dict(UserProfile.MEMBERSHIP_CHOICES):
            return JsonResponse({
                'success': False,
                'message': 'Invalid membership tier'
            }, status=400)
            
        # Get the user and profile
        user = get_object_or_404(User, id=user_id)
        
        # Get or create profile if it doesn't exist
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)
            
        old_tier = profile.membership_tier
        
        # Update membership
        profile.membership_tier = new_tier
        profile.membership_start_date = timezone.now()
        profile.membership_end_date = timezone.now() + timezone.timedelta(days=365)
        profile.save()
        
        # Clear all access caches for this user
        try:
            cache.delete(f'user_videos_{user.id}')
            logger.info(f"Cleared cache for user {user.id}")
        except Exception as cache_error:
            logger.warning(f"Failed to clear cache: {str(cache_error)}")
            
        # Log the change
        AuditLog.objects.create(
            user=request.user,
            action_type='membership_change',
            action=f'Updated membership from {old_tier} to {new_tier}',
            ip_address=get_client_ip(request),
            status='success',
            related_user=user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Membership updated successfully',
            'new_tier': profile.get_membership_tier_display(),
            'membership_end_date': profile.membership_end_date.isoformat() if profile.membership_end_date else None
        })
    except Exception as e:
        logger.error(f"Error updating membership: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'An error occurred while updating membership: {str(e)}'
        }, status=500)

@login_required
def handle_payment_proof(request, proof_id, action):
    if not is_admin(request.user):
        return JsonResponse({
            'success': False,
            'message': "You don't have permission to perform this action."
        }, status=403)
    
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        }, status=405)
    
    if action not in ['approve', 'reject']:
        return JsonResponse({
            'success': False,
            'message': 'Invalid action'
        }, status=400)
    
    try:
        with transaction.atomic():
            proof = get_object_or_404(PaymentProof.objects.select_related('user__profile'), id=proof_id)
            
            if proof.status != 'pending':
                return JsonResponse({
                    'success': False,
                    'message': f'Payment proof has already been {proof.status}'
                }, status=400)
            
            # Update proof status
            proof.status = action
            proof.processed_by = request.user
            proof.processed_at = timezone.now()
            proof.save()
            
            # If approved, update user's membership
            if action == 'approve':
                profile = proof.user.profile
                profile.membership_tier = proof.requested_tier
                profile.membership_start_date = timezone.now()
                profile.membership_end_date = timezone.now() + timezone.timedelta(days=365)
                profile.save()
            
            # Log the action
            AuditLog.objects.create(
                user=request.user,
                action_type='payment_proof',
                action=f'{action.title()}d payment proof for user {proof.user.username}',
                ip_address=get_client_ip(request),
                status='success'
            )
            
            # Clear cache
            cache.delete(f'user_videos_{proof.user.id}')
            
            return JsonResponse({
                'success': True,
                'message': f'Payment proof {action}d successfully',
                'status': proof.status
            })
            
    except PaymentProof.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Payment proof not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in handle_payment_proof: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error processing payment proof: {str(e)}'
        }, status=500)

@login_required
def user_management(request):
    users = User.objects.exclude(is_superuser=True).select_related('profile').prefetch_related('payment_proofs').order_by('-date_joined')
    
    # Get counts for each payment proof status
    pending_count = PaymentProof.objects.filter(status='pending').count()
    approved_count = PaymentProof.objects.filter(status='approved').count()
    rejected_count = PaymentProof.objects.filter(status='rejected').count()
    
    users_data = []
    for user in users:
        payment_proofs = list(user.payment_proofs.all().order_by('-uploaded_at'))
        latest_proof = payment_proofs[0] if payment_proofs else None
        
        users_data.append({
            'user': user,
            'profile': user.profile,
            'payment_proofs': payment_proofs,
            'latest_proof': latest_proof,
            'pending_proofs': sum(1 for p in payment_proofs if p.status == 'pending'),
            'approved_proofs': sum(1 for p in payment_proofs if p.status == 'approved'),
            'rejected_proofs': sum(1 for p in payment_proofs if p.status == 'rejected'),
        })
    
    context = {
        'users_data': users_data,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    
    return render(request, 'dashboard/user_management.html', context)

@login_required
def process_payment_proof(request, proof_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
        
    try:
        proof = PaymentProof.objects.get(id=proof_id)
        action = request.POST.get('action')
        feedback = request.POST.get('feedback', '')
        
        # Get client IP for audit logging
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
            
        # Create base audit log for the action
        audit_log = AuditLog.objects.create(
            user=proof.user,
            action_type='payment',
            action=f'Payment proof {action}ed by {request.user.username}',
            ip_address=ip_address,
            status=action,
            related_user=request.user
        )
        
        if action == 'approve':
            # Update IP address in approve method's audit logs
            with transaction.atomic():
                proof.approve(request.user, feedback)
                
                # Update IP for both audit logs created in approve method
                AuditLog.objects.filter(
                    user=proof.user,
                    timestamp__gte=timezone.now() - timezone.timedelta(seconds=5)
                ).update(ip_address=ip_address)
                
            message = 'Payment proof approved successfully'
            
        elif action == 'reject':
            # Update IP address in reject method's audit log
            with transaction.atomic():
                proof.reject(request.user, feedback)
                
                # Update IP for audit log created in reject method
                AuditLog.objects.filter(
                    user=proof.user,
                    timestamp__gte=timezone.now() - timezone.timedelta(seconds=5)
                ).update(ip_address=ip_address)
                
            message = 'Payment proof rejected successfully'
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except PaymentProof.DoesNotExist:
        return JsonResponse({'error': 'Payment proof not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def video_management(request):
    if not request.user.is_staff:
        return redirect('admin_dashboard')  # Change 'dashboard' to 'admin_dashboard'

    videos = Video.objects.all().order_by('-created_at')
    context = {
        'videos': videos,
        'active_section': 'videos'
    }
    return render(request, 'dashboard/video_management.html', context)

# Helper function to log activities
def log_activity(user, action_type, action_detail, request=None):
    """Log user activities"""
    try:
        client_ip = get_client_ip(request) if request else None
        AuditLog.objects.create(
            user=user,
            action_type=action_type,
            action_detail=action_detail,
            ip_address=client_ip
        )
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")

@login_required
def add_video_form(request):
    """Render the form for adding a free video"""
    if request.method == 'GET':
        return render(request, 'dashboard/add_video.html')
    elif request.method == 'POST':
        try:
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            url = request.POST.get('url')
            
            if not title or not url:
                error_msg = "Title and URL are required fields"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('video_management')
                
            if Video.objects.filter(url=url).exists():
                error_msg = "A video with this URL already exists"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('video_management')
            
            video = Video()
            video.title = title
            video.description = description
            video.url = url
            video.is_active = True
            video.is_free = True
            video.save()
            
            log_activity(request.user, 'video_add', f'Added new free video: {video.title}', request)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Video added successfully to free course',
                    'video_id': video.id
                })
            
            messages.success(request, "Video added successfully to free course")
            return redirect('video_management')
            
        except Exception as e:
            logger.error(f"Error adding video: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f"An error occurred: {str(e)}"}, status=400)
            messages.error(request, f"An error occurred while adding the video: {str(e)}")
            return redirect('video_management')

@login_required
def get_video(request, video_id):
    """Get video details"""
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    try:
        video = get_object_or_404(Video, id=video_id)
        data = {
            'id': video.id,
            'title': video.title,
            'description': video.description,
            'url': video.url,
            'membership_tier': video.membership_tier,
            'views': video.views,
            'is_active': video.is_active,
        }
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error getting video details: {str(e)}")
        return JsonResponse({'error': str(e)}, status=404)

@login_required
def toggle_video_status(request, video_id):
    """Toggle video active status"""
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    if request.method == 'POST':
        try:
            video = get_object_or_404(Video, id=video_id)
            video.is_active = not video.is_active
            video.save()
            
            action = "Activated" if video.is_active else "Deactivated"
            AuditLog.objects.create(
                user=request.user,
                action=f"{action} video: {video.title}",
                action_type='video_update',
                ip_address=get_client_ip(request)
            )
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error toggling video status: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    
    return HttpResponseForbidden("Invalid request method")

@login_required
def delete_video(request, video_id):
    """Delete a video"""
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    if request.method == 'POST':
        try:
            video = get_object_or_404(Video, id=video_id)
            title = video.title
            
            video.delete()
            
            AuditLog.objects.create(
                user=request.user,
                action=f"Deleted video: {title}",
                action_type='video_delete',
                ip_address=get_client_ip(request)
            )
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error deleting video: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    
    return HttpResponseForbidden("Invalid request method")

@login_required
def payment_management(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    # Get all payment proofs
    payment_proofs = PaymentProof.objects.select_related('user', 'processed_by').order_by('-uploaded_at')
    
    # Get counts
    pending_count = payment_proofs.filter(status='pending').count()
    approved_count = payment_proofs.filter(status='approved').count()
    rejected_count = payment_proofs.filter(status='rejected').count()
    
    # Calculate total revenue from approved payments
    total_revenue = 0
    for proof in payment_proofs.filter(status='approved'):
        total_revenue += PaymentProof.TIER_PRICING.get(proof.requested_tier, 0)

    # Calculate monthly revenue for the last 6 months
    monthly_revenue = []
    for i in range(5, -1, -1):
        month_start = timezone.now() - timezone.timedelta(days=30 * i)
        month_end = month_start + timezone.timedelta(days=30)
        month_proofs = payment_proofs.filter(
            status='approved',
            uploaded_at__gte=month_start,
            uploaded_at__lt=month_end
        )
        revenue = sum(PaymentProof.TIER_PRICING.get(proof.requested_tier, 0) for proof in month_proofs)
        monthly_revenue.append({
            'month': month_start.strftime('%B'),
            'revenue': revenue
        })
    
    context = {
        'payment_proofs': payment_proofs,
        'total_revenue': total_revenue,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'monthly_revenue': monthly_revenue,
        'active_section': 'payments',
        'tier_pricing': PaymentProof.TIER_PRICING
    }
    
    return render(request, 'dashboard/payment_management.html', context)

@login_required
def approve_payment(request, payment_id):
    if not request.user.is_staff:
        return redirect('dashboard')
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        payment = PaymentProof.objects.get(id=payment_id)
        
        if payment.status != 'pending':
            return JsonResponse({'error': 'Payment has already been processed'}, status=400)
        
        # Get amount from tier pricing
        amount = PaymentProof.TIER_PRICING.get(payment.requested_tier, 0)
        
        # Update payment status
        payment.status = 'approved'
        payment.processed_by = request.user
        payment.processed_at = timezone.now()
        payment.save()
        
        # Update user's membership
        user_profile = payment.user.profile
        user_profile.membership_tier = payment.requested_tier
        user_profile.membership_start_date = timezone.now()
        user_profile.membership_end_date = timezone.now() + timezone.timedelta(days=PaymentProof.TIER_DURATION.get(payment.requested_tier, 0))
        user_profile.save()
        
        # Log the activity
        AuditLog.objects.create(
            user=request.user,
            action_type='payment',
            action=f'Approved payment proof #{payment_id} for {payment.requested_tier} membership (${amount})',
            ip_address=get_client_ip(request),
            related_user=payment.user
        )
        
        messages.success(request, f'Payment approved successfully. User membership updated to {payment.requested_tier}.')
        return JsonResponse({
            'success': True,
            'message': 'Payment approved successfully',
            'amount': amount,
            'tier': payment.requested_tier
        })
        
    except PaymentProof.DoesNotExist:
        return JsonResponse({'error': 'Payment proof not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def reject_payment(request, payment_id):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        payment = PaymentProof.objects.get(id=payment_id)
        feedback = request.POST.get('feedback', '')
        
        payment.status = 'rejected'
        payment.reviewed_at = timezone.now()
        payment.reviewed_by = request.user
        payment.admin_feedback = feedback
        payment.save()
        
        # Log activity
        log_activity(
            request.user,
            'payment',
            f'Rejected payment proof from {payment.user.username}'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Payment rejected successfully'
        })
        
    except PaymentProof.DoesNotExist:
        return JsonResponse({'error': 'Payment proof not found'}, status=404)
    except Exception as e:
        logger.error(f"Error rejecting payment: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
def reports(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    # Get basic statistics
    total_users = User.objects.filter(is_superuser=False).count()
    active_users = User.objects.filter(is_active=True).count()
    
    # Get membership statistics
    membership_stats = []
    for tier, label in UserProfile.MEMBERSHIP_CHOICES:
        count = UserProfile.objects.filter(membership_tier=tier).count()
        membership_stats.append({
            'membership_tier': tier,
            'count': count
        })

    # Get payment statistics
    approved_payments = PaymentProof.objects.filter(status='approved')
    total_revenue = sum(payment.get_amount() for payment in approved_payments)
    recent_payments = approved_payments.order_by('-uploaded_at')[:5]
    
    # Calculate monthly revenue for the last 6 months
    today = timezone.now()
    monthly_revenue = []
    for i in range(5, -1, -1):
        start_date = today - timedelta(days=today.day) - timedelta(days=30*i)
        end_date = start_date + timedelta(days=32)
        end_date = end_date.replace(day=1)
        month_payments = approved_payments.filter(uploaded_at__gte=start_date, uploaded_at__lt=end_date)
        monthly_revenue.append(sum(payment.get_amount() for payment in month_payments))
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'membership_stats': json.dumps(membership_stats),  # Convert to JSON for JavaScript
        'total_revenue': total_revenue,
        'recent_payments': recent_payments,
        'monthly_revenue': json.dumps(monthly_revenue),  # Convert to JSON for JavaScript
        'active_section': 'reports'
    }
    
    return render(request, 'dashboard/reports.html', context)

@login_required
def admin_settings(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    if request.method == 'POST':
        # Handle settings update
        try:
            # Update site settings
            site_name = request.POST.get('site_name')
            maintenance_mode = request.POST.get('maintenance_mode') == 'on'
            registration_enabled = request.POST.get('registration_enabled') == 'on'
            
            # Save settings to cache or database
            cache.set('site_name', site_name)
            cache.set('maintenance_mode', maintenance_mode)
            cache.set('registration_enabled', registration_enabled)
            
            messages.success(request, 'Settings updated successfully')
            return redirect('admin_settings')
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')
    
    # Get current settings
    context = {
        'site_name': cache.get('site_name', 'Video Streaming Site'),
        'maintenance_mode': cache.get('maintenance_mode', False),
        'registration_enabled': cache.get('registration_enabled', True),
        'active_section': 'settings'
    }
    
    return render(request, 'dashboard/settings.html', context)

@login_required
def admin_profile(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    if request.method == 'POST':
        try:
            user = request.user
            # Update profile information
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.email = request.POST.get('email', user.email)
            
            # Handle password change if provided
            new_password = request.POST.get('new_password')
            if new_password:
                if request.POST.get('confirm_password') == new_password:
                    user.set_password(new_password)
                    messages.success(request, 'Password updated successfully. Please log in again.')
                else:
                    messages.error(request, 'Passwords do not match')
                    return redirect('admin_profile')
            
            user.save()
            messages.success(request, 'Profile updated successfully')
            
            # If password was changed, redirect to login
            if new_password:
                return redirect('login')
            return redirect('admin_profile')
            
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
    
    context = {
        'active_section': 'profile'
    }
    
    return render(request, 'dashboard/profile.html', context)

@login_required
def update_profile(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    try:
        user = request.user
        
        # Get client IP for audit logging
        ip_address = get_client_ip(request)
        
        # Track changed fields for audit log
        changed_fields = []
        
        # Update profile fields
        if 'first_name' in request.POST:
            if user.first_name != request.POST['first_name']:
                changed_fields.append('first_name')
                user.first_name = request.POST['first_name']
        
        if 'last_name' in request.POST:
            if user.last_name != request.POST['last_name']:
                changed_fields.append('last_name')
                user.last_name = request.POST['last_name']
        
        if 'email' in request.POST:
            if user.email != request.POST['email']:
                changed_fields.append('email')
                user.email = request.POST['email']
        
        # Save user changes if any fields were updated
        if changed_fields:
            user.save()
            
            # Create audit log entry
            AuditLog.objects.create(
                user=user,
                action_type='profile_update',
                action=f"Updated profile fields: {', '.join(changed_fields)}",
                ip_address=ip_address,
                status='success'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully'
            })
        else:
            return JsonResponse({
                'success': True,
                'message': 'No changes detected'
            })
            
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        
        # Log the error
        AuditLog.objects.create(
            user=request.user,
            action_type='profile_update',
            action=f"Failed to update profile: {str(e)}",
            ip_address=ip_address,
            status='failed'
        )
        
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while updating your profile'
        }, status=500)

@login_required
def audit_logs(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    # Get filters from request
    action_type = request.GET.get('action_type', '')
    user_id = request.GET.get('user_id', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    # Base queryset
    activities = AuditLog.objects.select_related('user', 'related_user').order_by('-timestamp')

    # Apply filters
    if action_type:
        activities = activities.filter(action_type=action_type)
    if user_id:
        activities = activities.filter(user_id=user_id)
    if start_date:
        try:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            activities = activities.filter(timestamp__date__gte=start_date)
        except ValueError:
            pass
    if end_date:
        try:
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
            activities = activities.filter(timestamp__date__lte=end_date)
        except ValueError:
            pass

    # Add color-coded badges and format action details
    for activity in activities:
        activity.badge_color = {
            'login': 'info',
            'logout': 'secondary',
            'register': 'success',
            'profile_update': 'primary',
            'payment': 'warning',
            'video_upload': 'info',
            'video_delete': 'danger',
            'membership_change': 'primary',
            'settings_update': 'info',
            'user_activation': 'success',
            'user_deactivation': 'danger',
        }.get(activity.action_type, 'secondary')
        
        # Format action detail based on action type
        if activity.action_type == 'membership_change':
            activity.action_detail = f"Changed to {activity.action.split(' to ')[1]}"
        elif activity.action_type == 'payment':
            activity.action_detail = f"Payment for {activity.action}"
        elif activity.action_type == 'video_upload':
            activity.action_detail = f"Uploaded {activity.action}"
        elif activity.action_type == 'video_delete':
            activity.action_detail = f"Deleted {activity.action}"
        else:
            activity.action_detail = activity.action

    # Get unique users for filter dropdown
    users = User.objects.filter(
        audit_logs__isnull=False
    ).distinct().order_by('username')

    # Get unique action types for filter dropdown
    action_types = AuditLog.ACTION_TYPES

    context = {
        'activities': activities,
        'users': users,
        'action_types': action_types,
        'current_filters': {
            'action_type': action_type,
            'user_id': user_id,
            'start_date': start_date,
            'end_date': end_date,
        },
        'active_section': 'audit_logs'
    }

    return render(request, 'dashboard/audit_logs.html', context)

def export_logs(logs, format):
    """
    Export audit logs in CSV or PDF format
    
    Args:
        logs: QuerySet of AuditLog objects to export
        format: String indicating the export format ('csv' or 'pdf')
    
    Returns:
        HttpResponse with the appropriate content type and file
        HttpResponseBadRequest if format is invalid or export fails
    """
    try:
        if format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['User', 'Action', 'Type', 'IP Address', 'Timestamp'])
            
            for log in logs:
                writer.writerow([
                    log.user.username if log.user else 'Anonymous',
                    log.action,
                    log.action_type,
                    log.ip_address or 'N/A',
                    log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            return response
        
        elif format == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="audit_logs.pdf"'
            
            # Create PDF document
            doc = SimpleDocTemplate(response, pagesize=letter)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            elements.append(Paragraph('Audit Logs', styles['Title']))
            elements.append(Spacer(1, 12))
            
            # Create table data
            data = [['User', 'Action', 'Type', 'IP Address', 'Timestamp']]
            for log in logs:
                data.append([
                    log.user.username if log.user else 'Anonymous',
                    log.action,
                    log.action_type,
                    log.ip_address or 'N/A',
                    log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                ])
            
            # Create table
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 12),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
            
            try:
                # Build PDF
                doc.build(elements)
                return response
            except Exception as e:
                logger.error(f"Failed to build PDF: {str(e)}")
                return HttpResponseBadRequest("Failed to generate PDF. Please try again or use CSV format.")
        
        else:
            return HttpResponseBadRequest("Invalid export format. Supported formats: csv, pdf")
            
    except Exception as e:
        logger.error("Failed to export logs: " + str(e))
        return HttpResponseBadRequest("Failed to export logs. Please try again later.")

@login_required
def dashboard_stats(request, timeframe):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    try:
        now = timezone.now()
        if timeframe == 'week':
            start_date = now - timezone.timedelta(days=7)
            interval = timezone.timedelta(days=1)
            date_format = '%A'
        elif timeframe == 'month':
            start_date = now - timezone.timedelta(days=30)
            interval = timezone.timedelta(days=1)
            date_format = '%b %d'
        else:  # year
            start_date = now - timezone.timedelta(days=365)
            interval = timezone.timedelta(days=30)
            date_format = '%B'
        
        # Initialize data points
        data_points = []
        current_date = start_date
        
        while current_date <= now:
            next_date = current_date + interval
            
            # Get user count
            user_count = User.objects.filter(
                date_joined__gte=current_date,
                date_joined__lt=next_date
            ).count()
            
            # Get revenue
            revenue = PaymentProof.objects.filter(
                status='approved',
                uploaded_at__gte=current_date,
                uploaded_at__lt=next_date
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            data_points.append({
                'date': current_date.strftime(date_format),
                'users': user_count,
                'revenue': float(revenue)
            })
            
            current_date = next_date
        
        return JsonResponse({
            'labels': [point['date'] for point in data_points],
            'users': [point['users'] for point in data_points],
            'revenue': [point['revenue'] for point in data_points]
        })
        
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def dashboard_events(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    
    response = StreamingHttpResponse(event_stream(request), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    return response

def event_stream(request):
    """Generate server-sent events"""
    while True:
        # Get latest statistics
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'pending_payments': PaymentProof.objects.filter(status='pending').count(),
            'total_revenue': float(PaymentProof.objects.filter(status='approved').aggregate(Sum('amount'))['amount__sum'] or 0)
        }
        
        # Get latest activities
        activities = AuditLog.objects.select_related('user', 'related_user').order_by('-timestamp')[:5]
        activity_data = [{
            'user': activity.user.username,
            'action': activity.action,
            'action_type': activity.action_type,
            'badge_color': {
                'login': 'info',
                'logout': 'secondary',
                'register': 'success',
                'profile_update': 'primary',
                'payment': 'warning',
                'video_upload': 'info',
                'video_delete': 'danger',
                'membership_change': 'primary',
                'settings_update': 'info',
                'user_activation': 'success',
                'user_deactivation': 'danger',
            }.get(activity.action_type, 'secondary')
        } for activity in activities]
        
        data = {
            'stats': stats,
            'activities': activity_data
        }
        
        yield f"data: {json.dumps(data)}\n\n"
        time.sleep(5)  # Update every 5 seconds

@login_required
def course_list(request):
    """Display list of available courses"""
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        # Get user's profile
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'membership_tier': 'regular'}
        )
        
        # Get all active courses
        courses = Course.objects.filter(is_active=True).order_by('order')
        
        context = {
            'membership_tier': profile.membership_tier,
            'membership_display': profile.get_membership_tier_display(),
            'membership_end_date': profile.membership_end_date,
            'is_membership_active': profile.is_membership_active(),
            'courses': courses,
        }
        
        return render(request, 'video_streaming/course_list.html', context)
    except Exception as e:
        logger.error(f"Error in course_list: {str(e)}")
        messages.error(request, "An error occurred while loading courses. Please try again later.")
        return redirect('index')

@login_required
def course_detail(request, course_id):
    """Display course details with videos based on membership tier"""
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        # Get course
        course = get_object_or_404(Course, id=course_id, is_active=True)
        
        # Get user's profile
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'membership_tier': 'regular'}
        )
        
        # Get videos accessible to user based on membership tier
        accessible_videos = course.get_videos_by_tier(profile.membership_tier)
        
        # Get all videos for the course to show locked ones
        all_videos = course.videos.filter(is_active=True).order_by('order')
        
        # Get user progress for accessible videos
        video_progress = {}
        progress_objects = VideoProgress.objects.filter(
            user=request.user,
            video__in=accessible_videos
        )
        
        for progress in progress_objects:
            video_progress[progress.video.id] = {
                'progress': progress.progress,
                'completed': progress.completed
            }
        
        context = {
            'course': course,
            'membership_tier': profile.membership_tier,
            'membership_display': profile.get_membership_tier_display(),
            'is_membership_active': profile.is_membership_active(),
            'accessible_videos': accessible_videos,
            'all_videos': all_videos,
            'video_progress': video_progress,
        }
        
        return render(request, 'video_streaming/course_detail.html', context)
    except Exception as e:
        logger.error(f"Error in course_detail: {str(e)}")
        messages.error(request, "An error occurred while loading the course. Please try again later.")
        return redirect('course_list')

def free_video_player(request, video_id):
    """View for playing free videos without requiring login"""
    try:
        video = get_object_or_404(MegaVideo, id=video_id)
        
        # Check if the video is marked as free
        if not video.is_free:
            # If not free, redirect to login
            return redirect(f'{reverse("login")}?next={reverse("video_player", kwargs={"video_id": video_id})}')        
        
        try:
            # Get the video URL using the universal streaming service
            from .services.mega_service import MegaService
            mega_service = MegaService()
            stream_url = mega_service.get_universal_streaming_url(
                video.mega_file_link, 
                video.video_source, 
                request.user
            )
            
            # Debug logging
            logger.info(f"Free video - Original URL: {video.mega_file_link}")
            logger.info(f"Free video - Video source: {video.video_source}")
            logger.info(f"Free video player using URL: {stream_url}")
            
            # If no URL is available, raise an exception
            if not stream_url:
                raise Exception("No valid video URL available")
                
            # Get other free videos for navigation
            videos = MegaVideo.objects.filter(is_free=True).order_by('title')
            video_list = list(videos)
            
            try:
                current_index = video_list.index(video)
                previous_video = video_list[current_index - 1] if current_index > 0 else None
                next_video = video_list[current_index + 1] if current_index < len(video_list) - 1 else None
            except (ValueError, IndexError):
                # Handle case where video might not be in the list
                previous_video = None
                next_video = None
            
            # Get thumbnail URL
            thumbnail_url = video.get_thumbnail_url()
            
            # Ensure default thumbnail exists
            import os
            static_dir = os.path.join(settings.BASE_DIR, 'myapp', 'static', 'img')
            if not os.path.exists(static_dir):
                os.makedirs(static_dir, exist_ok=True)
                
            default_thumbnail = os.path.join(static_dir, 'default-thumbnail.jpg')
            if not os.path.exists(default_thumbnail):
                try:
                    from PIL import Image, ImageDraw, ImageFont
                    img = Image.new('RGB', (640, 360), color=(33, 37, 41))
                    d = ImageDraw.Draw(img)
                    d.text((320, 180), "Video", fill=(255, 255, 255), anchor="mm")
                    img.save(default_thumbnail)
                except Exception as e:
                    logger.error(f"Error creating default thumbnail: {str(e)}")
            
            # Prepare context for template
            context = {
                'video': video,
                'streaming_url': stream_url,
                'previous_video': previous_video,
                'next_video': next_video,
                'videos': video_list,
                'current_tier': 'Free',
                'thumbnail_url': thumbnail_url
            }
            
            # Log the streaming URL for debugging
            logger.info(f"Free video player using URL: {stream_url}")
            
            # Use the new simple_free_player.html template which provides multiple playback options
            return render(request, 'video_player/simple_free_player.html', context)
            
        except Exception as e:
            logger.error(f"Error streaming free video: {str(e)}")
            messages.error(request, "Unable to play video. Please try again.")
            return redirect('free_course')
            
    except Exception as e:
        logger.error(f"Error in free_video_player: {str(e)}")
        messages.error(request, "An error occurred while loading the video.")
        return redirect('free_course')

@login_required
def video_player(request, video_id):
    try:
        video = get_object_or_404(MegaVideo, id=video_id)
        
        # Check membership tier access
        if not request.user.profile.membership_tier in ['diamond'] and video.membership_tier == 'diamond':
            return render(request, 'video_streaming/upgrade_required.html', {
                'current_tier': request.user.profile.get_membership_tier_display(),
                'required_tier': 'Diamond'
            })
        
        if not request.user.profile.membership_tier in ['vip', 'diamond'] and video.membership_tier == 'vip':
            return render(request, 'video_streaming/upgrade_required.html', {
                'current_tier': request.user.profile.get_membership_tier_display(),
                'required_tier': 'VIP'
            })
        
        try:
            # Get stream URL with user context
            stream_url = video.get_stream_url(request.user)
            if not stream_url:
                raise Exception("Unable to generate streaming URL")

            # Get previous and next videos of the same tier
            videos = MegaVideo.objects.filter(membership_tier=video.membership_tier).order_by('title')
            video_list = list(videos)
            current_index = video_list.index(video)
            
            previous_video = video_list[current_index - 1] if current_index > 0 else None
            next_video = video_list[current_index + 1] if current_index < len(video_list) - 1 else None
            
            # Log video access
            AuditLog.objects.create(
                user=request.user,
                action_type='video_access',
                action=f'Accessed video: {video.title}',
                ip_address=get_client_ip(request),
                status='success'
            )
            
            context = {
                'video': video,
                'stream_url': stream_url,
                'previous_video': previous_video,
                'next_video': next_video,
                'videos': video_list,
                'current_tier': request.user.profile.get_membership_tier_display()
            }
            
            return render(request, 'video_streaming/video_player.html', context)
            
        except Exception as e:
            logger.error(f"Error streaming video: {str(e)}")
            messages.error(request, "Unable to play video. Please try again.")
            return redirect('video_streaming_course')
            
    except Exception as e:
        logger.error(f"Error in video_player: {str(e)}")
        messages.error(request, "An error occurred while loading the video.")
        return redirect('video_streaming_course')

@login_required
@require_http_methods(["POST"])
def track_video_analytics(request, video_id):
    """Track video analytics events"""
    try:
        data = json.loads(request.body)
        video = get_object_or_404(Video, id=video_id)
        session = get_object_or_404(VideoStreamSession, id=data.get('session_id'))
        
        if session.user != request.user:
            return HttpResponseForbidden("Invalid session")
        
        video.track_analytics(
            session=session,
            event_type=data.get('event_type'),
            position=data.get('position'),
            duration=data.get('duration'),
            metadata=data.get('metadata')
        )
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error tracking analytics: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def manage_drive_folders(request):
    """View for managing Google Drive folders"""
    try:
        # Get all folders with video count
        folders = GoogleDriveFolder.objects.annotate(
            video_count=Count('googledrivevideo')
        ).order_by('-created_at')
        
        # Handle search
        search_query = request.GET.get('search', '')
        if search_query:
            folders = folders.filter(name__icontains=search_query)
        
        # Pagination
        paginator = Paginator(folders, 12)  # Show 12 folders per page
        page_number = request.GET.get('page', 1)
        folders_page = paginator.get_page(page_number)
        
        context = {
            'folders': folders_page,
            'search_query': search_query,
        }
        
        return render(request, 'admin/drive_folder_management.html', context)
        
    except Exception as e:
        logger.error(f"Error in manage_drive_folders: {str(e)}")
        messages.error(request, "An error occurred while loading the folders.")
        return redirect('dashboard_videos')

@login_required
def create_drive_folder(request):
    """Create a new Google Drive folder connection"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        name = request.POST.get('name')
        folder_id = request.POST.get('folder_id')
        parent_id = request.POST.get('parent_id')
        
        if not name or not folder_id:
            return JsonResponse({
                'success': False,
                'message': 'Name and folder ID are required'
            }, status=400)
        
        # Extract folder ID from URL if needed
        clean_folder_id = extract_folder_id(folder_id)
        clean_parent_id = extract_folder_id(parent_id) if parent_id else None
        
        # Check if folder already exists
        existing_folder = GoogleDriveFolder.objects.filter(folder_id=clean_folder_id).first()
        if existing_folder:
            # Update the existing folder
            existing_folder.name = name
            if clean_parent_id:
                parent_folder = get_object_or_404(GoogleDriveFolder, folder_id=clean_parent_id)
                existing_folder.parent_folder = parent_folder
            existing_folder.is_active = True
            existing_folder.save()
            
            # Log the update
            AuditLog.objects.create(
            user=request.user,
                action_type='folder_update',
                action=f'Updated Google Drive folder connection: {name}',
                ip_address=get_client_ip(request),
                status='success'
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Folder updated successfully',
                'folder': {
                    'id': existing_folder.id,
                    'name': existing_folder.name,
                    'folder_id': existing_folder.folder_id
                }
            })
        
        # Get parent folder if specified
        parent_folder = None
        if clean_parent_id:
            parent_folder = get_object_or_404(GoogleDriveFolder, folder_id=clean_parent_id)
        
        # Create new folder
        folder = GoogleDriveFolder.objects.create(
            name=name,
            folder_id=clean_folder_id,
            parent_folder=parent_folder
        )
        
        # Log the creation
        AuditLog.objects.create(
                    user=request.user,
            action_type='folder_create',
            action=f'Created Google Drive folder connection: {name}',
            ip_address=get_client_ip(request),
            status='success'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Folder created successfully',
            'folder': {
                'id': folder.id,
                'name': folder.name,
                'folder_id': folder.folder_id
            }
        })
    except Exception as e:
        logger.error(f"Error creating/updating drive folder: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# Add this helper function
def extract_folder_id(folder_url_or_id: str) -> str:
    """Extract the folder ID from a Google Drive folder URL or ID"""
    if 'drive.google.com' in folder_url_or_id:
        # Extract folder ID from URL
        if '/folders/' in folder_url_or_id:
            folder_id = folder_url_or_id.split('/folders/')[-1].split('?')[0]
            return folder_id
    return folder_url_or_id

@login_required
def sync_drive_folder(request, folder_id):
    """Sync videos from a Google Drive folder"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Get the folder from database
        folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
        
        # Initialize Google Drive service
        drive_service = GoogleDriveService()
        
        # Sync folder using the folder's Google Drive ID
        result = drive_service.sync_folder(folder.folder_id)
        
        # Update folder in database
        folder.last_synced = timezone.now()
        folder.save()
        
        # Log the sync
        AuditLog.objects.create(
            user=request.user,
            action_type='folder_sync',
            action=f'Synced Google Drive folder: {folder.name}',
            ip_address=get_client_ip(request),
            status='success'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Folder synced successfully',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error syncing folder {folder_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error syncing drive folder: {str(e)}'
        }, status=500)

@login_required
def update_video_progress(request, video_id):
    """Update video progress for a user"""
    if request.method == 'POST':
        try:
            video = get_object_or_404(GoogleDriveVideo, id=video_id)
            data = json.loads(request.body)
            
            # Get or create progress record
            progress, created = VideoProgress.objects.get_or_create(
                user=request.user,
                video=video,
                defaults={
                    'progress': 0,
                    'current_time': 0
                }
            )
            
            # Update progress
            progress.update_progress(
                current_time=data.get('current_time', 0),
                duration=data.get('duration', 0)
            )
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            logger.error(f"Error updating video progress: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    elif request.method == 'GET':
        try:
            progress = VideoProgress.objects.get(
                user=request.user,
                video_id=video_id
            )
            return JsonResponse({
                'success': True,
                'current_time': progress.current_time,
                'progress': progress.progress
            })
        except VideoProgress.DoesNotExist:
            return JsonResponse({
                'success': True,
                'current_time': 0,
                'progress': 0
            })
        except Exception as e:
            logger.error(f"Error getting video progress: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@login_required
def upgrade_membership(request):
    """Display membership upgrade options"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        # Get user's profile
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'membership_tier': 'regular'}
        )
        
        context = {
            'membership_tier': profile.membership_tier,
            'membership_display': profile.get_membership_tier_display(),
            'is_membership_active': profile.is_membership_active(),
            'membership_end_date': profile.membership_end_date,
        }
        
        return render(request, 'video_streaming/upgrade_membership.html', context)
    except Exception as e:
        logger.error(f"Error in upgrade_membership: {str(e)}")
        messages.error(request, "An error occurred. Please try again later.")
        return redirect('index')

@login_required
def submit_payment_proof(request):
    """Submit payment proof for membership upgrade"""
    if not request.user.is_authenticated or request.method != 'POST':
        return redirect('upgrade_membership')
    
    try:
        # Get requested tier
        requested_tier = request.POST.get('requested_tier')
        if requested_tier not in ['vip', 'diamond']:
            messages.error(request, "Invalid membership tier selected.")
            return redirect('upgrade_membership')
        
        # Check if payment proof image was uploaded
        if 'payment_proof' not in request.FILES:
            messages.error(request, "Please upload a payment proof image.")
            return redirect('upgrade_membership')
        
        # Create payment proof
        payment_proof = PaymentProof.objects.create(
            user=request.user,
            image=request.FILES['payment_proof'],
            requested_tier=requested_tier,
            status='pending'
        )
        
        messages.success(request, "Your payment proof has been submitted and is pending approval.")
        return redirect('upgrade_membership')
    except Exception as e:
        logger.error(f"Error in submit_payment_proof: {str(e)}")
        messages.error(request, "An error occurred while submitting your payment proof. Please try again.")
        return redirect('upgrade_membership')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)  # Only allow staff/admin users
def bulk_video_upload(request):
    """Admin interface for uploading multiple videos at once"""
    if request.method == 'POST':
        try:
            course_id = request.POST.get('course')
            membership_tier = request.POST.get('membership_tier')
            
            if not course_id or not membership_tier:
                messages.error(request, "Please select a course and membership tier.")
                return redirect('bulk_video_upload')
            
            course = get_object_or_404(Course, id=course_id)
            
            # Get the highest order value for existing videos in this course
            highest_order = Video.objects.filter(course=course).aggregate(models.Max('order'))['order__max'] or 0
            order_counter = highest_order + 1
            
            # Process each uploaded video
            for i, file_key in enumerate(request.FILES):
                if file_key.startswith('video_'):
                    file = request.FILES[file_key]
                    title_key = f'title_{i}'
                    description_key = f'description_{i}'
                    duration_key = f'duration_{i}'
                    
                    title = request.POST.get(title_key, f'Video {order_counter}')
                    description = request.POST.get(description_key, '')
                    duration = request.POST.get(duration_key, '20 mins')
                    
                    # Save the video file
                    file_path = default_storage.save(f'videos/{file.name}', file)
                    file_url = settings.MEDIA_URL + file_path
                    
                    # Create video object
                    Video.objects.create(
                        title=title,
                        description=description,
                        url=file_url,
                        membership_tier=membership_tier,
                        duration=duration,
                        course=course,
                        order=order_counter
                    )
                    
                    order_counter += 1
            
            messages.success(request, f"Successfully uploaded {order_counter - highest_order - 1} videos.")
            return redirect('video_management')
        except Exception as e:
            logger.error(f"Error in bulk_video_upload: {str(e)}")
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('bulk_video_upload')
    else:
        courses = Course.objects.filter(is_active=True)
        return render(request, 'admin/bulk_video_upload.html', {'courses': courses})

@login_required
def video_streaming_index(request):
    """
    View for displaying the video streaming index page with videos categorized by membership tier.
    """
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        # Get user's profile
        profile = request.user.profile
        
        # Get videos based on membership tier
        regular_videos = Video.objects.filter(tier__tier='regular', is_active=True)
        vip_videos = Video.objects.filter(tier__tier='vip', is_active=True)
        diamond_videos = Video.objects.filter(tier__tier='diamond', is_active=True)
        
        context = {
            'regular_videos': regular_videos,
            'vip_videos': vip_videos,
            'diamond_videos': diamond_videos,
            'user': request.user
        }
        
        # Log this activity
        log_activity(
            request.user,
            'video_access',
            'Accessed video streaming index page'
        )
        
        return render(request, 'video_streaming/index.html', context)
    except Exception as e:
        logger.error(f"Error in video_streaming_index: {str(e)}")
        messages.error(request, "An error occurred while loading the video library. Please try again later.")
        return redirect('index')

@login_required
def video_streaming_course(request):
    """View for the video streaming course page"""
    try:
        # Check if user has a profile
        try:
            profile = request.user.profile
        except AttributeError:
            # If user doesn't have a profile, create a default context
            logger.warning(f"User {request.user.username} doesn't have a profile")
            context = {
                'regular_videos': MegaVideo.objects.filter(membership_tier='regular'),
                'vip_videos': MegaVideo.objects.filter(membership_tier='vip'),
                'diamond_videos': MegaVideo.objects.filter(membership_tier='diamond'),
                'user_profile': None,
                'current_tier': 'Regular',  # Default tier
                'has_pending_payment': False
            }
            return render(request, 'video_streaming/course.html', context)
        
        # Get all videos grouped by membership tier
        regular_videos = MegaVideo.objects.filter(membership_tier='regular')
        vip_videos = MegaVideo.objects.filter(membership_tier='vip')
        diamond_videos = MegaVideo.objects.filter(membership_tier='diamond')
        
        # Add accessibility flag to each video
        for video in regular_videos:
            video.is_accessible = True
            
        for video in vip_videos:
            video.is_accessible = profile.membership_tier in ['vip', 'diamond']
            
        for video in diamond_videos:
            video.is_accessible = profile.membership_tier == 'diamond'
        
        # Check if user has any pending payment proofs
        from .models import PaymentProof
        has_pending_payment = PaymentProof.objects.filter(
            user=request.user,
            status='pending'
        ).exists()
        
        context = {
            'regular_videos': regular_videos,
            'vip_videos': vip_videos,
            'diamond_videos': diamond_videos,
            'user_profile': profile,
            'current_tier': profile.get_membership_tier_display(),
            'has_pending_payment': has_pending_payment
        }
        
        # Log the page view
        AuditLog.objects.create(
            user=request.user,
            action_type='page_view',
            action='Viewed video streaming course page',
            ip_address=get_client_ip(request),
            status='success'
        )
        
        return render(request, 'video_streaming/course.html', context)
        
    except Exception as e:
        logger.error(f"Error in video streaming course view: {str(e)}")
        messages.error(request, "An error occurred while loading the course content.")
        return redirect('index')

@login_required
def get_folder_videos(request, folder_id):
    """API endpoint to get videos from a folder"""
    try:
        folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
        
        # Check access
        if not folder.can_access(request.user):
            return JsonResponse({
                'success': False,
                'message': 'Access denied'
            }, status=403)
        
        # Get videos from Google Drive
        drive_service = GoogleDriveService()
        videos = drive_service.list_folder_videos(folder.folder_id)
        
        # Log the access
        AuditLog.objects.create(
            user=request.user,
            action_type='folder_access',
            action=f'Accessed folder: {folder.name}',
            ip_address=get_client_ip(request),
            status='success'
        )
        
        return JsonResponse({
            'success': True,
            'videos': videos
        })
        
    except Exception as e:
        logger.error(f"Error getting folder videos: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error loading videos'
        }, status=500)

@login_required
def video_list(request, video_id=None):
    """
    View for displaying the video list page with a main player and sidebar.
    """
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        # Get user's profile
        profile = request.user.profile
        
        # Get current video if video_id is provided, otherwise get first accessible video
        if video_id:
            current_video = get_object_or_404(Video, id=video_id)
            if not profile.can_access_video(current_video):
                messages.error(request, "You don't have access to this video. Please upgrade your membership.")
                return redirect('video_list')
        else:
            current_video = profile.get_accessible_videos().first()
            if not current_video:
                messages.error(request, "No videos available for your membership tier.")
                return redirect('index')
        
        # Get all videos for the sidebar
        all_videos = Video.objects.filter(is_active=True).order_by('order', 'upload_date')
        
        # Get completed and in-progress videos
        completed_videos = profile.get_completed_videos()
        in_progress_videos = profile.get_in_progress_videos()
        
        # Get next video
        next_video = profile.get_next_video(current_video)
        can_access_next = next_video and profile.can_access_video(next_video)
        
        context = {
            'current_video': current_video,
            'all_videos': all_videos,
            'completed_videos': completed_videos,
            'in_progress_videos': in_progress_videos,
            'next_video': next_video,
            'can_access_next': can_access_next,
            'user': request.user
        }
        
        # Log this activity
        log_activity(
            request.user,
            'video_access',
            f'Accessed video: {current_video.title}'
        )
        
        return render(request, 'video_streaming/video-list.html', context)
    except Exception as e:
        logger.error(f"Error in video_list: {str(e)}")
        messages.error(request, "An error occurred while loading the video. Please try again later.")
        return redirect('index')

def free_course(request):
    """View for the free course page that shows regular videos without requiring login"""
    # Get all free videos (non-premium content) from both Video and MegaVideo models
    from .models import MegaVideo
    
    # Get free videos from MegaVideo model
    free_mega_videos = MegaVideo.objects.filter(is_free=True).order_by('-created_at')
    
    # Log the number of free videos found for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Found {len(free_mega_videos)} free MEGA videos")
    for video in free_mega_videos:
        logger.info(f"Free MEGA video: {video.title}, is_free={video.is_free}")
    
    # Force refresh of the videos from the database
    from django.db import connection
    connection.close()
    
    # Get the videos again after refreshing the connection
    free_mega_videos = MegaVideo.objects.filter(is_free=True).order_by('-created_at')
    
    context = {
        'videos': free_mega_videos,
        'title': 'Free Course',
        'description': 'Access our free video content without registration',
    }
    
    return render(request, 'free_course.html', context)

def get_client_ip(request):
    """
    Helper function to get client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

@login_required
def oauth2callback(request):
    """Handle Google OAuth2 callback"""
    # The OAuth flow will handle the response automatically
    # This view just needs to exist to handle the redirect
    return HttpResponse("Authentication successful! You can close this window.")

@login_required
def delete_drive_folder(request, folder_id):
    """Delete a Google Drive folder connection"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        # Get the folder
        folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
        
        # Store folder info for logging
        folder_name = folder.name
        
        # Clear any cache related to this folder
        cache.delete(f'folder_videos_{folder_id}')
        cache.delete(f'folder_info_{folder_id}')
        
        # Delete folder from database
        folder.delete()
        
        # Log the deletion
        AuditLog.objects.create(
            user=request.user,
            action_type='folder_delete',
            action=f'Deleted Google Drive folder connection: {folder_name}',
            ip_address=get_client_ip(request),
            status='success'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Folder deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting folder {folder_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting folder: {str(e)}'
        }, status=500)

@staff_member_required
def drive_folder_management(request):
    """View for managing MEGA videos"""
    # Redirect to the new MEGA video management view
    return redirect('mega_video_management')

@staff_member_required
def update_folder_tier(request, folder_id):
    """Update folder membership tier and handle access changes"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        with transaction.atomic():
            folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
            new_tier = request.POST.get('membership_tier')
            
            if new_tier not in dict(GoogleDriveFolder.MEMBERSHIP_TIERS):
                return JsonResponse({'error': 'Invalid membership tier'}, status=400)
            
            old_tier = folder.membership_tier
            folder.membership_tier = new_tier
            folder.save()
            
            # Update access cache
            folder.update_access_cache()
            
            # Log the change
            AuditLog.objects.create(
                user=request.user,
                action_type='folder_update',
                action=f'Updated folder "{folder.name}" membership tier from {old_tier} to {new_tier}',
                ip_address=get_client_ip(request),
                status='success'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Membership tier updated successfully'
            })
            
    except Exception as e:
        logger.error(f"Error updating folder tier: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@staff_member_required
def folder_videos(request, folder_id):
    """View for displaying videos in a folder"""
    folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
    videos = folder.googledrivevideo_set.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(videos, 20)  # Show 20 videos per page
    page_number = request.GET.get('page', 1)
    videos_page = paginator.get_page(page_number)
    
    context = {
        'folder': folder,
        'videos': videos_page,
    }
    
    return render(request, 'admin/folder_videos.html', context)

@staff_member_required
def sync_folder(request, folder_id):
    """View for syncing a Google Drive folder"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
    
    try:
        # Initialize Google Drive service
        try:
            drive_service = GoogleDriveService()
        except Exception as service_error:
            logger.error(f"Failed to initialize Google Drive service: {str(service_error)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to initialize Google Drive service. Please check your credentials.'
            }, status=500)
        
        try:
            # Start sync process with improved functionality
            sync_result = drive_service.sync_folder(folder.folder_id)
            
            # Create audit log entry with detailed information
            AuditLog.objects.create(
                user=request.user,
                action_type='folder_sync',
                action=f'Synced folder: {folder.name}',
                ip_address=get_client_ip(request),
                status=sync_result['status'],
                details=json.dumps({
                    'total_videos': sync_result['total_videos'],
                    'new_videos': sync_result['new_videos'],
                    'updated_videos': sync_result['updated_videos'],
                    'deleted_videos': sync_result['deleted_videos'],
                    'sync_duration': sync_result['sync_duration'],
                    'errors': sync_result['errors'] if sync_result['errors'] else None
                })
            )
            
            # Prepare response message
            message = (
                f"Successfully synced {sync_result['total_videos']} videos "
                f"({sync_result['new_videos']} new, {sync_result['updated_videos']} updated, "
                f"{sync_result['deleted_videos']} deleted)"
            )
            
            if sync_result['errors']:
                message += f" with {len(sync_result['errors'])} errors"
            
            return JsonResponse({
                'status': sync_result['status'],
                'message': message,
                'videos_count': sync_result['total_videos'],
                'last_synced': sync_result['timestamp'],
                'details': {
                    'new_videos': sync_result['new_videos'],
                    'updated_videos': sync_result['updated_videos'],
                    'deleted_videos': sync_result['deleted_videos'],
                    'sync_duration': f"{sync_result['sync_duration']:.2f} seconds",
                    'errors': sync_result['errors'] if sync_result['errors'] else None
                }
            })
            
        except Exception as sync_error:
            error_msg = f"Error syncing folder {folder.name}: {str(sync_error)}"
            logger.error(error_msg)
            
            # Log the error
            AuditLog.objects.create(
                user=request.user,
                action_type='folder_sync',
                action=f'Failed to sync folder: {folder.name}',
                ip_address=get_client_ip(request),
                status='error',
                details=json.dumps({'error': str(sync_error)})
            )
            
            return JsonResponse({
                'status': 'error',
                'message': error_msg
            }, status=500)
            
    except GoogleDriveFolder.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Folder not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in sync_folder view: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }, status=500)

@staff_member_required
def delete_folder(request, folder_id):
    """View for deleting a folder"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
    
    try:
        # Store folder info for logging
        folder_name = folder.name
        
        # Delete the folder and its videos
        folder.delete()
        
        # Log the deletion
        AuditLog.objects.create(
            user=request.user,
            action_type='folder_delete',
            action=f'Deleted folder: {folder_name}',
            status='success'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Folder deleted successfully'
        })
        
    except Exception as e:
        # Log the error
        AuditLog.objects.create(
            user=request.user,
            action_type='folder_delete',
            action=f'Failed to delete folder: {folder.name}. Error: {str(e)}',
            status='error'
        )
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@staff_member_required
def folder_events(request):
    """Server-Sent Events endpoint for real-time folder updates"""
    def event_stream():
        last_check = time.time()
        
        while True:
            # Check for updates every 5 seconds
            current_time = time.time()
            if current_time - last_check >= 5:
                folders = GoogleDriveFolder.objects.filter(
                    last_synced__gte=last_check
                ).annotate(
                    video_count=Count('googledrivevideo')
                )
                
                for folder in folders:
                    data = {
                        'folder_id': folder.id,
                        'video_count': folder.video_count,
                        'last_synced': folder.last_synced.isoformat() if folder.last_synced else None
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                
                last_check = current_time
            
            time.sleep(1)
    
    return StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)  # Only allow staff/admin users
def folder_videos_list(request):
    """Admin view for managing Google Drive videos"""
    try:
        # Get all folders
        folders = GoogleDriveFolder.objects.all().order_by('-created_at')
        
        # Update video counts for each folder
        for folder in folders:
            folder.update_video_count()
        
        # Add pagination
        paginator = Paginator(folders, 10)  # Show 10 folders per page
        page = request.GET.get('page')
        folders = paginator.get_page(page)
        
        context = {
            'folders': folders,
            'section': 'drive_folders',
            'title': 'Google Drive Folder Management'
        }
        
        return render(request, 'admin/drive_folder_management.html', context)
        
    except Exception as e:
        logger.error(f"Error in folder_videos_list: {str(e)}")
        messages.error(request, "An error occurred while loading the folders.")
        return redirect('admin_dashboard')

@staff_member_required
def folder_videos_detail(request, folder_id):
    """View for displaying videos in a specific folder"""
    folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
    videos = folder.googledrivevideo_set.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(videos, 20)  # Show 20 videos per page
    page_number = request.GET.get('page', 1)
    videos_page = paginator.get_page(page_number)
    
    context = {
        'folder': folder,
        'videos': videos_page,
    }
    
    return render(request, 'dashboard/folder_videos_detail.html', context)

@staff_member_required
def manage_folder_access(request, folder_id):
    folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            
            if action == 'grant':
                FolderAccess.objects.create(
                    user=user,
                    folder=folder,
                    granted_by=request.user
                )
                messages.success(request, f"Access granted to {user.username}")
                
            elif action == 'revoke':
                FolderAccess.objects.filter(
                    user=user,
                    folder=folder
                ).update(is_active=False)
                messages.success(request, f"Access revoked from {user.username}")
                
            # Log the action
            AuditLog.objects.create(
                user=request.user,
                action_type='folder_access',
                action=f"{action} access for {user.username} to {folder.name}",
                status='success'
            )
            
        except User.DoesNotExist:
            messages.error(request, "User not found")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    # Get current access list
    access_list = FolderAccess.objects.filter(folder=folder, is_active=True)
    pending_requests = AccessRequest.objects.filter(folder=folder, status='pending')
    
    context = {
        'folder': folder,
        'access_list': access_list,
        'pending_requests': pending_requests,
        'users': User.objects.filter(is_active=True)
    }
    
    return render(request, 'admin/manage_folder_access.html', context)

@login_required
def request_folder_access(request, folder_id):
    folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
    
    if request.method == 'POST':
        # Check if request already exists
        existing_request = AccessRequest.objects.filter(
            user=request.user,
            folder=folder,
            status='pending'
        ).exists()
        
        if existing_request:
            messages.info(request, "You already have a pending request for this folder")
        else:
            AccessRequest.objects.create(
                user=request.user,
                folder=folder,
                notes=request.POST.get('notes', '')
            )
            messages.success(request, "Access request submitted successfully")
    
    return redirect('folder_detail', folder_id=folder_id)

@login_required
def folder_detail(request, folder_id):
    """User view for accessing folder videos"""
    try:
        folder = get_object_or_404(GoogleDriveFolder, id=folder_id)
        
        # Check if user has access to this folder
        if not folder.can_access(request.user):
            messages.error(request, "You don't have access to this folder.")
            return redirect('video_streaming_course')
        
        # Get videos from the folder
        videos = folder.googledrivevideo_set.all().order_by('title')
        
        context = {
            'folder': folder,
            'videos': videos
        }
        
        return render(request, 'video_streaming/folder_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error in folder_detail: {str(e)}")
        messages.error(request, "An error occurred while loading the folder.")
        return redirect('video_streaming_course')

@staff_member_required
def add_folder(request):
    """Add a new Google Drive folder"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    try:
        name = request.POST.get('name')
        folder_id = request.POST.get('folder_id')
        membership_tier = request.POST.get('membership_tier', 'regular')
        
        if not name or not folder_id:
            return JsonResponse({
                'success': False,
                'message': 'Name and folder ID are required'
            }, status=400)
        
        # Extract folder ID from URL if needed
        if 'drive.google.com' in folder_id:
            folder_id = extract_folder_id(folder_id)
        
        # Check if folder already exists
        if GoogleDriveFolder.objects.filter(folder_id=folder_id).exists():
            return JsonResponse({
                'success': False,
                'message': 'A folder with this ID already exists'
            }, status=400)
        
        # Create new folder
        folder = GoogleDriveFolder.objects.create(
            name=name,
            folder_id=folder_id,
            membership_tier=membership_tier,
            is_active=True
        )
        
        # Log the action
        AuditLog.objects.create(
            user=request.user,
            action_type='folder_create',
            action=f'Created folder: {name}',
            ip_address=get_client_ip(request),
            status='success'
        )
        
        # Try to sync the folder immediately
        try:
            drive_service = GoogleDriveService()
            sync_result = drive_service.sync_folder(folder_id)
            folder.last_synced = timezone.now()
            folder.save()
        except Exception as e:
            logger.warning(f"Initial folder sync failed: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': 'Folder added successfully',
            'folder': {
                'id': folder.id,
                'name': folder.name,
                'membership_tier': folder.get_membership_tier_display()
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding folder: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error adding folder: {str(e)}'
        }, status=500)

@login_required
def video_streaming(request, video_id):
    """Stream video from Google Drive with support for range requests"""
    try:
        # Get video record
        video = get_object_or_404(MegaVideo, id=video_id)
        
        # Initialize Google Drive service
        drive_service = GoogleDriveService()
        
        # Get range header if present
        range_header = request.META.get('HTTP_RANGE')
        
        # Get video stream info
        stream_info = drive_service.get_video_stream(
            video.drive_file_id,
            request.user,
            range_header
        )
        
        # Create response
        response = StreamingHttpResponse(
            stream_info['request'].execute(),
            content_type=stream_info['mime_type']
        )
        
        # Set content length
        response['Content-Length'] = stream_info['size']
        
        # Handle range request
        if range_header:
            response.status_code = 206
            response['Content-Range'] = f'bytes {stream_info["start"]}-{stream_info["end"]}/{stream_info["size"]}'
            response['Accept-Ranges'] = 'bytes'
        
        # Set cache control headers
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        
        # Log video access
        log_activity(
            request.user,
            'video_stream',
            f'Streamed video: {video.title}',
            request
        )
        
        return response
        
    except PermissionError:
        return JsonResponse({
            'status': 'error',
            'message': 'You do not have permission to access this video'
        }, status=403)
    except Exception as e:
        logger.error(f"Error streaming video {video_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Error streaming video'
        }, status=500)

@login_required
def videos_index(request):
    """Redirect to video streaming course page"""
    return redirect('video_streaming_course')

def add_video_form(request):
    """Render the form for adding a free video"""
    if request.method == 'GET':
        return render(request, 'dashboard/add_video.html')
    elif request.method == 'POST':
        try:
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            url = request.POST.get('url')
            
            if not title or not url:
                error_msg = "Title and URL are required fields"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('video_management')
                
            if Video.objects.filter(url=url).exists():
                error_msg = "A video with this URL already exists"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('video_management')
            
            video = Video()
            video.title = title
            video.description = description
            video.url = url
            video.is_active = True
            video.is_free = True
            video.save()
            
            log_activity(request.user, 'video_add', f'Added new free video: {video.title}', request)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Video added successfully to free course',
                    'video_id': video.id
                })
            
            messages.success(request, "Video added successfully to free course")
            return redirect('video_management')
            
        except Exception as e:
            logger.error(f"Error adding video: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f"An error occurred: {str(e)}"}, status=400)
            messages.error(request, f"An error occurred while adding the video: {str(e)}")
            return redirect('video_management')

@login_required
def get_all_video_paths():
    """Get all video paths from the upload directory"""
    video_dir = os.path.join(settings.MEDIA_ROOT, 'videos')
    if not os.path.exists(video_dir):
        os.makedirs(video_dir)
    
    video_paths = []
    for root, dirs, files in os.walk(video_dir):
        for file in files:
            if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, video_dir)
                video_paths.append({
                    'path': rel_path,
                    'size': os.path.getsize(full_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(full_path))
                })
    return video_paths

@login_required
@require_http_methods(['POST'])
def delete_mega_video(request, video_id):
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'error': "Permission denied"}, status=403)
    try:
        video = get_object_or_404(MegaVideo, id=video_id)
        video.delete()
        AuditLog.objects.create(user=request.user, action=f"Deleted MEGA video: {video.title}", action_type='mega_video_delete')
        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.error(f"Error deleting MEGA video: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)

@login_required
def membership_page(request):
    """View for the membership upgrade page"""
    # Get user's current membership status
    profile = request.user.profile
    
    # Check for pending payments
    pending_payment = PaymentProof.objects.filter(
        user=request.user,
        status='pending'
    ).first()
    
    context = {
        'pending_payment': pending_payment,
    }
    
    return render(request, 'membership.html', context)

@login_required
def upgrade_membership(request):
    """Handle membership upgrade requests"""
    if request.method == 'POST':
        tier = request.POST.get('tier')
        
        # Validate tier
        if tier not in ['vip', 'diamond']:
            messages.error(request, 'Invalid membership tier selected.')
            return redirect('membership_page')
            
        # Check if user already has a pending payment
        existing_payment = PaymentProof.objects.filter(
            user=request.user,
            status='pending'
        ).first()
        
        if existing_payment:
            messages.warning(request, 'You already have a pending payment. Please wait for it to be processed.')
            return redirect('membership_page')
            
        # Create new payment proof
        payment = PaymentProof.objects.create(
            user=request.user,
            requested_tier=tier
        )
        
        # Log the upgrade request
        AuditLog.objects.create(
            user=request.user,
            action_type='membership_change',
            action=f'Requested upgrade to {tier} membership',
            status='pending'
        )
        
        messages.success(request, 'Your upgrade request has been submitted. Please upload your payment proof.')
        return redirect('upload_payment_proof', payment_id=payment.id)
        
    return redirect('membership_page')

@login_required
def upload_payment_proof(request, payment_id):
    """Handle payment proof upload"""
    try:
        payment = PaymentProof.objects.get(id=payment_id, user=request.user)
    except PaymentProof.DoesNotExist:
        messages.error(request, 'Payment record not found.')
        return redirect('membership_page')
        
    if request.method == 'POST':
        form = PaymentProofForm(request.POST, request.FILES, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payment proof uploaded successfully. Please wait for admin approval.')
            return redirect('membership_page')
    else:
        form = PaymentProofForm(instance=payment)
        
    context = {
        'form': form,
        'payment': payment
    }
    return render(request, 'upload_payment_proof.html', context)

@login_required
def membership_upgrade(request):
    """Handle membership upgrade requests"""
    # Get user's current membership tier
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    # Get available tiers (excluding current tier and lower tiers)
    current_tier_index = dict(UserProfile.MEMBERSHIP_CHOICES).get(profile.membership_tier, 0)
    available_tiers = [
        (tier[0], tier[1]) 
        for tier in UserProfile.MEMBERSHIP_CHOICES 
        if dict(UserProfile.MEMBERSHIP_CHOICES).get(tier[0], 0) > current_tier_index
    ]
    
    if not available_tiers:
        messages.warning(request, 'You already have the highest membership tier available.')
        return redirect('course_video_library')
    
    if request.method == 'POST':
        form = MembershipUpgradeRequestForm(request.POST, request.FILES)
        if form.is_valid():
            # Create upgrade request
            upgrade_request = form.save(commit=False)
            upgrade_request.user = request.user
            upgrade_request.desired_tier = request.POST.get('desired_tier')
            upgrade_request.status = 'pending'
            upgrade_request.save()
            
            # Log the request
            AuditLog.objects.create(
                user=request.user,
                action='membership_upgrade_request',
                details=f'Requested upgrade to {upgrade_request.get_desired_tier_display()}'
            )
            
            # Send email notification to admin
            subject = f'New Membership Upgrade Request from {request.user.username}'
            message = f"""
            A new membership upgrade request has been submitted:
            
            User: {request.user.username}
            Current Tier: {profile.get_membership_tier_display()}
            Requested Tier: {upgrade_request.get_desired_tier_display()}
            Reason: {upgrade_request.reason}
            
            Please review this request in the admin panel.
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                fail_silently=False,
            )
            
            messages.success(request, 'Your upgrade request has been submitted and is pending review.')
            return redirect('course_video_library')
    else:
        form = MembershipUpgradeRequestForm()
    
    # Get user's pending requests
    pending_requests = MembershipUpgradeRequest.objects.filter(
        user=request.user,
        status='pending'
    ).order_by('-created_at')
    
    context = {
        'form': form,
        'available_tiers': available_tiers,
        'current_tier': profile.get_membership_tier_display(),
        'pending_requests': pending_requests,
    }
    return render(request, 'myapp/membership_upgrade.html', context)
