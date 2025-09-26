"""
This file contains a fixed implementation of the add_video function
to properly handle video creation and ensure videos are added to the free course.

Instructions:
1. Copy the function below and replace the existing add_video function in your views.py file
2. Make sure to import all necessary models and functions
"""

@login_required
def add_video(request):
    """Add a new video"""
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
        messages.error(request, "Invalid request method")
        return redirect('video_management')
    
    try:
        # Extract form data
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        url = request.POST.get('url')
        
        # Basic validation
        if not title or not url:
            error_msg = "Title and URL are required fields"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('video_management')
        
        # Create new video - simplified approach to avoid model field mismatches
        video = Video()
        video.title = title
        video.description = description
        video.url = url
        video.is_active = True
        video.is_free = True
        video.save()
        
        # Log the activity
        log_activity(
            request.user,
            'video_add',
            f'Added new free video: {video.title}',
            request
        )
        
        # Check if it's an AJAX request
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
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f"An error occurred: {str(e)}"
            }, status=400)
        
        messages.error(request, f"An error occurred while adding the video: {str(e)}")
        return redirect('video_management')
