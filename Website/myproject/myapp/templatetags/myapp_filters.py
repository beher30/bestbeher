"""
Custom template filters for the payment management dashboard and membership-based access control and course progress tracking.
"""
from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get a dictionary item by key."""
    return dictionary.get(key, 0) if isinstance(dictionary, dict) else 0

@register.filter
def div(value, arg):
    """Divide the value by the argument."""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0

@register.filter
def has_access(user, content):
    """Check if a user has access to content based on their membership tier."""
    if not user.is_authenticated:
        return False
        
    tier_levels = {
        'regular': 0,
        'vip': 1,
        'diamond': 2
    }
    
    user_tier_level = tier_levels.get(user.membership_tier, 0)
    content_tier_level = tier_levels.get(content.required_tier, 0)
    
    return user_tier_level >= content_tier_level

@register.filter
def has_started(user, course):
    """Check if a user has started a course."""
    if not user.is_authenticated:
        return False
    
    return user.course_progress.filter(course=course).exists()

@register.filter
def has_completed(user, content):
    """Check if a user has completed a video or course."""
    if not user.is_authenticated:
        return False
    
    if hasattr(content, 'videos'):  # It's a course
        total_videos = content.videos.count()
        if total_videos == 0:
            return False
        completed_videos = user.completed_videos.filter(course=content).count()
        return completed_videos == total_videos
    else:  # It's a video
        return user.completed_videos.filter(id=content.id).exists()

@register.filter
def course_progress(user, course):
    """Get the user's progress percentage for a course."""
    if not user.is_authenticated:
        return 0
    
    total_videos = course.videos.count()
    if total_videos == 0:
        return 0
        
    completed_videos = user.completed_videos.filter(course=course).count()
    return int((completed_videos / total_videos) * 100)

@register.filter
def completed_videos_count(user, course):
    """Get the number of completed videos in a course."""
    if not user.is_authenticated:
        return 0
    
    return user.completed_videos.filter(course=course).count()

@register.filter
def get_prev_accessible_video(user, current_video):
    """Get the previous accessible video in the course."""
    if not user.is_authenticated:
        return None
        
    prev_videos = current_video.course.videos.filter(
        order__lt=current_video.order
    ).order_by('-order')
    
    for video in prev_videos:
        if has_access(user, video):
            return video
    
    return None

@register.filter
def get_next_accessible_video(user, current_video):
    """Get the next accessible video in the course."""
    if not user.is_authenticated:
        return None
        
    next_videos = current_video.course.videos.filter(
        order__gt=current_video.order
    ).order_by('order')
    
    for video in next_videos:
        if has_access(user, video):
            return video
    
    return None
