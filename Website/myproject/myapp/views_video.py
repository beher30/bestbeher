from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt
from .models import Video, VideoStreamSession, VideoProgress, MembershipAccess
from .services.mega_service import MegaService
import jwt
import time
import json
import logging

logger = logging.getLogger(__name__)

# Helper to generate a time-limited token
SECRET_KEY = settings.SECRET_KEY
TOKEN_EXPIRY_SECONDS = 60 * 10  # 10 minutes

def generate_video_token(user, video_id):
    payload = {
        'user_id': user.id,
        'video_id': video_id,
        'iat': int(time.time()),
        'exp': int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_video_token(token, user, video_id):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return (
            payload['user_id'] == user.id and
            payload['video_id'] == video_id
        )
    except Exception:
        return False

@login_required
def stream_video(request, video_id):
    video = get_object_or_404(Video, pk=video_id)
    user = request.user
    session, created = VideoStreamSession.objects.get_or_create(
        user=request.user,
        video=video,
        defaults={
            'expires_at': timezone.now() + timezone.timedelta(hours=4),
            'is_active': True,
            'signed_url': video.url,
            'watermark_data': json.dumps({
                'text': f'{request.user.username} - {request.user.email}',
                'position': 'random',
                'opacity': 0.7
            })
        }
    )
    
    if not session.is_active:
        # Reactivate session if it's inactive
        session.is_active = True
        session.expires_at = timezone.now() + timezone.timedelta(hours=4)
        session.save()
    
    # Generate a token for secure playback
    token = generate_video_token(request.user, video_id)
    
    # Redirect to video player with token
    return HttpResponseRedirect(f"{reverse('video_player')}?video_id={video_id}&token={token}")

@login_required
def mega_video_player(request, video_id):
    """Render the Plyr.js video player for MEGA videos"""
    video = get_object_or_404(Video, id=video_id)
    
    # Check if user has access to this video based on membership tier
    user_profile = request.user.profile
    if not user_profile.can_access_video(video):
        return HttpResponseForbidden("Your membership tier does not allow access to this video.")
    
    # Get or create a stream session
    session, created = VideoStreamSession.objects.get_or_create(
        user=request.user,
        video=video,
        defaults={
            'expires_at': timezone.now() + timezone.timedelta(hours=4),
            'is_active': True,
            'signed_url': video.url,
            'watermark_data': json.dumps({
                'text': f'{request.user.username} - {request.user.email}',
                'position': 'random',
                'opacity': 0.7
            })
        }
    )
    
    # Get or create video progress
    progress, created = VideoProgress.objects.get_or_create(
        user=request.user,
        video=video,
        defaults={
            'progress': 0,
            'current_time': 0,
            'completed': False
        }
    )
    
    # Generate secure video URL
    secure_url = video.get_stream_url(request.user)
    
    context = {
        'video': video,
        'session': session,
        'progress': progress,
        'secure_url': secure_url,
        'watermark_data': json.loads(session.watermark_data) if session.watermark_data else {}
    }
    
    return render(request, 'video_player/plyr_player.html', context)

@login_required
@xframe_options_exempt
def mega_video_embed(request):
    """Embed view for MEGA videos with secure token validation"""
    token = request.GET.get('token')
    if not token:
        return HttpResponseForbidden("Invalid access token")
    
    # Validate token
    mega_service = MegaService()
    token_data = mega_service.validate_secure_token(token)
    
    if not token_data:
        return HttpResponseForbidden("Invalid or expired token")
    
    # Check if user ID in token matches current user
    if token_data.get('user_id') != request.user.id:
        return HttpResponseForbidden("Token user mismatch")
    
    # Get the MEGA URL from token data
    mega_url = token_data.get('mega_url')
    if not mega_url:
        return HttpResponseForbidden("Invalid video link")
    
    # Generate watermark data
    watermark_data = {
        'text': f'{request.user.username} - {request.user.email}',
        'position': 'random',
        'opacity': 0.7,
        'session_id': token_data.get('session_id', '')
    }
    
    context = {
        'mega_url': mega_url,
        'watermark_data': watermark_data,
        'user': request.user
    }
    
    return render(request, 'video_player/mega_embed.html', context)

@login_required
def update_video_progress_api(request, video_id):
    """API endpoint to update video progress"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        current_time = float(data.get('current_time', 0))
        duration = float(data.get('duration', 0))
        completed = bool(data.get('completed', False))
        
        # Calculate progress percentage
        progress_percent = 0
        if duration > 0:
            progress_percent = min(100, (current_time / duration) * 100)
        
        # If we're at 95% or more, consider it completed
        if progress_percent >= 95:
            completed = True
        
        # Get or create progress record
        progress, created = VideoProgress.objects.get_or_create(
            user=request.user,
            video_id=video_id,
            defaults={
                'current_time': current_time,
                'progress': progress_percent,
                'completed': completed
            }
        )
        
        # Update existing record
        if not created:
            progress.current_time = current_time
            progress.progress = progress_percent
            progress.completed = completed
            progress.save()
        
        # Track analytics if available
        video = Video.objects.get(id=video_id)
        sessions = VideoStreamSession.objects.filter(
            user=request.user,
            video=video,
            is_active=True
        ).order_by('-created_at')
        
        if sessions.exists() and video.analytics_enabled:
            session = sessions.first()
            video.track_analytics(
                session=session,
                event_type='progress',
                position=current_time,
                duration=duration,
                metadata={'completed': completed, 'progress': progress_percent}
            )
        
        return JsonResponse({
            'status': 'success',
            'progress': progress_percent,
            'current_time': current_time,
            'completed': completed
        })
    
    except Exception as e:
        logger.error(f"Error updating video progress: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_video_token(request, video_id):
    # AJAX endpoint to get a secure token for video streaming
    video = get_object_or_404(Video, pk=video_id)
    user = request.user

    # Check if user has access to this video's tier
    access = MembershipAccess.objects.filter(
        user=user,
        tier=video.tier,
        is_active=True,
        expires_at__gt=timezone.now()
    ).first()

    if not access:
        return JsonResponse({'error': 'forbidden'}, status=403)

    token = generate_video_token(user, str(video.id))
    stream_url = reverse('stream_video', args=[video.id]) + f'?token={token}'
    return JsonResponse({'stream_url': stream_url})
