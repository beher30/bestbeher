"""
Fixed implementation of the add_video function to properly handle video creation
and display success/failure messages.
"""

def add_video(request):
    """Add a new video"""
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
        messages.error(request, "Invalid request method")
        return redirect('video_management')
    
    try:
        # Get form data
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        url = request.POST.get('url')
        
        # Validate required fields
        if not title or not url:
            raise ValueError("Title and URL are required fields")
        
        # Create new video - using only the fields we know exist in the model
        video = Video(
            title=title,
            description=description,
            url=url,
            is_active=True,
            is_free=True
        )
        
        # Save the video
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
