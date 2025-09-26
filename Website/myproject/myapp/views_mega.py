from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.views.decorators.clickjacking import xframe_options_exempt
from .models import MegaVideo, VideoProgress, AuditLog
from .services.mega_service import MegaService
from .views import get_client_ip
import logging
import json

logger = logging.getLogger(__name__)

@staff_member_required
def mega_video_management(request):
    """View for managing MEGA videos"""
    videos = MegaVideo.objects.all().order_by('-created_at')
    
    # Get video counts by tier
    regular_videos = videos.filter(membership_tier='regular').count()
    vip_videos = videos.filter(membership_tier='vip').count()
    diamond_videos = videos.filter(membership_tier='diamond').count()
    
    context = {
        'videos': videos,
        'regular_videos': regular_videos,
        'vip_videos': vip_videos,
        'diamond_videos': diamond_videos,
        'membership_tiers': MegaVideo.MEMBERSHIP_TIERS
    }
    
    return render(request, 'dashboard/mega_video_management.html', context)

@staff_member_required
def add_mega_video(request):
    """Add a new MEGA video"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        mega_link = request.POST.get('mega_link')
        membership_tier = request.POST.get('membership_tier', 'regular')
        thumbnail_url = request.POST.get('thumbnail_url', '')
        
        # Set is_free based on membership_tier
        is_free = membership_tier == 'free'
        
        if not title or not mega_link:
            messages.error(request, "Title and MEGA link are required.")
            return render(request, 'dashboard/add_mega_video.html', {
                'membership_tiers': MegaVideo.MEMBERSHIP_TIERS,
                'title': title,
                'description': description,
                'mega_link': mega_link,
                'membership_tier': membership_tier,
                'thumbnail_url': thumbnail_url,
                'is_free': is_free
            })
        
        # Validate MEGA link
        mega_service = MegaService()
        if not mega_service.is_file_link(mega_link):
            messages.error(request, "Invalid MEGA link. Please provide a valid MEGA file link (e.g., https://mega.nz/file/ABC...#XYZ...).")
            return render(request, 'dashboard/add_mega_video.html', {
                'membership_tiers': MegaVideo.MEMBERSHIP_TIERS,
                'title': title,
                'description': description,
                'mega_link': mega_link,
                'membership_tier': membership_tier,
                'thumbnail_url': thumbnail_url,
                'is_free': is_free
            })
        
        # Try to extract metadata from MEGA link
        try:
            # Create the video
            video = MegaVideo.objects.create(
                title=title,
                description=description,
                mega_file_link=mega_link,
                # If membership_tier is 'free', set it to 'regular' but mark as free
                membership_tier='regular' if membership_tier == 'free' else membership_tier,
                thumbnail_url=thumbnail_url,
                is_free=is_free
            )
            
            # Log the action
            AuditLog.objects.create(
                user=request.user,
                action_type='mega_video_create',
                action=f"Created MEGA video: {title}",
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f"MEGA video '{title}' was successfully added.")
            return redirect('mega_video_management')
        except Exception as e:
            logger.error(f"Error adding MEGA video: {str(e)}")
            messages.error(request, f"Error adding MEGA video: {str(e)}")
            return render(request, 'dashboard/add_mega_video.html', {
                'membership_tiers': MegaVideo.MEMBERSHIP_TIERS,
                'title': title,
                'description': description,
                'mega_link': mega_link,
                'membership_tier': membership_tier,
                'thumbnail_url': thumbnail_url,
                'is_free': is_free
            })
    
    return render(request, 'dashboard/add_mega_video.html', {
        'membership_tiers': MegaVideo.MEMBERSHIP_TIERS
    })

@staff_member_required
def edit_mega_video(request, video_id):
    """Edit an existing MEGA video"""
    video = get_object_or_404(MegaVideo, id=video_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        mega_link = request.POST.get('mega_link')
        membership_tier = request.POST.get('membership_tier', 'regular')
        thumbnail_url = request.POST.get('thumbnail_url', '')
        
        if not title or not mega_link:
            messages.error(request, "Title and MEGA link are required.")
            return render(request, 'dashboard/edit_mega_video.html', {
                'video': video,
                'membership_tiers': MegaVideo.MEMBERSHIP_TIERS
            })
        
        # Validate MEGA link
        mega_service = MegaService()
        if not mega_service.is_file_link(mega_link):
            messages.error(request, "Invalid MEGA link. Please provide a valid MEGA file link.")
            return render(request, 'dashboard/edit_mega_video.html', {
                'video': video,
                'membership_tiers': MegaVideo.MEMBERSHIP_TIERS
            })
        
        try:
            # Update the video
            video.title = title
            video.description = description
            video.mega_file_link = mega_link
            
            # Set is_free based on membership_tier
            is_free = membership_tier == 'free'
            
            # If membership_tier is 'free', set it to 'regular' but mark as free
            video.membership_tier = 'regular' if membership_tier == 'free' else membership_tier
            video.is_free = is_free
            video.thumbnail_url = thumbnail_url
            video.updated_at = timezone.now()
            video.save()
            
            messages.success(request, f"MEGA video '{title}' was successfully updated.")
            return redirect('mega_video_management')
        except Exception as e:
            logger.error(f"Error updating MEGA video: {str(e)}")
            messages.error(request, f"Error updating MEGA video: {str(e)}")
            return render(request, 'dashboard/edit_mega_video.html', {
                'video': video,
                'membership_tiers': MegaVideo.MEMBERSHIP_TIERS
            })
    
    return render(request, 'dashboard/edit_mega_video.html', {
        'video': video,
        'membership_tiers': MegaVideo.MEMBERSHIP_TIERS
    })

@staff_member_required
def delete_mega_video(request, video_id):
    """Delete a MEGA video"""
    video = get_object_or_404(MegaVideo, id=video_id)
    
    if request.method == 'POST':
        title = video.title
        try:
            video.delete()
            messages.success(request, f"MEGA video '{title}' was successfully deleted.")
        except Exception as e:
            logger.error(f"Error deleting MEGA video: {str(e)}")
            messages.error(request, f"Error deleting MEGA video: {str(e)}")
    
    return redirect('mega_video_management')

@login_required
def play_mega_video(request, video_id):
    """Play a MEGA video with Plyr.js"""
    video = get_object_or_404(MegaVideo, id=video_id)
    
    # Check if user has access to this video based on membership tier
    user_profile = request.user.profile
    user_tier = user_profile.membership_tier
    
    if not user_profile.is_membership_active():
        return HttpResponseForbidden("Your membership is not active.")
    
    # Check if user's tier allows access to this video
    if user_tier == 'regular' and video.membership_tier != 'regular':
        return HttpResponseForbidden("Your membership tier does not allow access to this video.")
    elif user_tier == 'vip' and video.membership_tier == 'diamond':
        return HttpResponseForbidden("Your membership tier does not allow access to this video.")
    
    # Generate secure URL for the video
    mega_service = MegaService()
    secure_token = mega_service.generate_secure_url(video.mega_file_link, request.user)
    
    # Extract the MEGA file ID and key from the URL
    file_id = mega_service.extract_mega_id(video.mega_file_link)
    key = mega_service.extract_mega_key(video.mega_file_link)
    
    if not file_id or not key:
        messages.error(request, "Invalid MEGA link format. Please contact support.")
        return redirect('video_streaming_course')
    
    # Construct a direct streaming URL for the MEGA player
    streaming_url = f"https://mega.nz/embed/{file_id}#{key}"
    
    # Generate watermark data
    watermark_data = {
        'text': f"{request.user.username} | {timezone.now().strftime('%Y-%m-%d')}",
        'position': 'random'
    }
    
    # Increment view count
    video.views += 1
    video.save()
    
    # Log video access
    AuditLog.objects.create(
        user=request.user,
        action_type='video_access',
        action=f'Accessed MEGA video: {video.title}',
        ip_address=get_client_ip(request),
        status='success'
    )
    
    context = {
        'video': video,
        'streaming_url': streaming_url,
        'watermark_data': watermark_data
    }
    
    return render(request, 'video_player/mega_player.html', context)

@login_required
def update_mega_video_progress(request, video_id):
    """Update progress for a MEGA video"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        current_time = float(data.get('current_time', 0))
        duration = float(data.get('duration', 0))
        completed = bool(data.get('completed', False))
        
        # Here you would update the progress in your database
        # This is a simplified example
        
        return JsonResponse({
            'status': 'success',
            'progress': min(100, (current_time / duration) * 100) if duration > 0 else 0,
            'current_time': current_time,
            'completed': completed
        })
    
    except Exception as e:
        logger.error(f"Error updating video progress: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@xframe_options_exempt
def mega_video_embed(request):
    """View for embedding MEGA videos with secure token"""
    token = request.GET.get('token')
    if not token:
        return HttpResponseForbidden("Access denied: Invalid token")
    
    mega_service = MegaService()
    try:
        # Validate token and get video URL
        data = mega_service.validate_secure_token(token)
        if not data or 'mega_link' not in data or 'user_id' not in data:
            return HttpResponseForbidden("Access denied: Invalid token data")
        
        mega_link = data['mega_link']
        user_id = data['user_id']
        
        # Get user info for watermark
        try:
            user = User.objects.get(id=user_id)
            watermark_text = f"{user.email}" if user.email else f"{user.username}"
        except User.DoesNotExist:
            watermark_text = "Unknown User"
        
        # Prepare watermark data
        watermark_data = {
            'text': watermark_text,
            'position': 'random',  # Can be: top-left, top-right, bottom-left, bottom-right, random
            'opacity': '0.7'
        }
        
        # Generate a direct streaming URL from the MEGA link
        mega_url = mega_service.get_streaming_url(mega_link, user)
        
        context = {
            'mega_url': mega_url,
            'watermark_data': watermark_data
        }
        
        return render(request, 'video_player/mega_embed.html', context)
    except Exception as e:
        logger.error(f"Error in mega_video_embed: {str(e)}")
        return HttpResponseForbidden("Access denied: Invalid token or server error")

@login_required
def stream_mega_video(request):
    """Stream a MEGA video using a secure token"""
    token = request.GET.get('token')
    if not token:
        return HttpResponseForbidden("Access denied: Invalid token")
    
    mega_service = MegaService()
    try:
        # Validate token and get video URL
        data = mega_service.validate_secure_token(token)
        if not data or 'mega_url' not in data or 'user_id' not in data:
            return HttpResponseForbidden("Access denied: Invalid token data")
        
        mega_url = data['mega_url']
        user_id = data['user_id']
        
        # Check if the requesting user is the same as the token user
        if request.user.id != user_id:
            return HttpResponseForbidden("Access denied: User mismatch")
        
        # Extract the MEGA file ID and key from the URL
        file_id = mega_service.extract_mega_id(mega_url)
        key = mega_service.extract_mega_key(mega_url)
        
        if not file_id or not key:
            return HttpResponseForbidden("Access denied: Invalid MEGA URL")
        
        # Construct a direct streaming URL for the MEGA player
        streaming_url = f"https://mega.nz/embed/{file_id}#{key}"
        
        context = {
            'streaming_url': streaming_url,
            'token': token,
            'user': request.user
        }
        
        return render(request, 'video_player/mega_player.html', context)
    except Exception as e:
        logger.error(f"Error in stream_mega_video: {str(e)}")
        return HttpResponseForbidden("Error streaming video: Server error")
