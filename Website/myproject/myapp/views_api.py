from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import MegaVideo, VideoProgress, AuditLog
from django.shortcuts import get_object_or_404
import json

def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@csrf_exempt
@login_required
def video_progress_api(request, video_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    user = request.user
    try:
        data = json.loads(request.body.decode('utf-8'))
        current_time = data.get('current_time')
        duration = data.get('duration')
        percent = data.get('percent')
        video = MegaVideo.objects.get(pk=video_id)
        progress, created = VideoProgress.objects.get_or_create(user=user, video_id=video.id)
        progress.current_time = current_time
        progress.duration = duration
        progress.percent = percent
        progress.last_updated = timezone.now()
        progress.save()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def delete_mega_video_api(request, video_id):
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'error': 'Permission denied'}, status=403)
        
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Method not allowed'}, status=405)
        
    try:
        video = get_object_or_404(MegaVideo, id=video_id)
        title = video.title  # Store title before deletion
        
        # Delete the video
        video.delete()
        
        # Log the deletion
        AuditLog.objects.create(
            user=request.user,
            action_type='video_delete',
            action=f'Deleted MEGA video: {title}',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Video "{title}" was successfully deleted'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=400)
