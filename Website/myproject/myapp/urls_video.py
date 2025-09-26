from django.urls import path
from . import views_video

urlpatterns = [
    # Original video endpoints
    path('videos/stream/<int:video_id>/', views_video.stream_video, name='stream_video'),
    path('videos/token/<int:video_id>/', views_video.get_video_token, name='get_video_token'),
    
    # MEGA video integration endpoints
    path('videos/mega/player/<int:video_id>/', views_video.mega_video_player, name='mega_video_player'),
    path('videos/mega/embed/', views_video.mega_video_embed, name='mega_video_embed'),
    path('api/videos/<int:video_id>/progress/', views_video.update_video_progress_api, name='update_video_progress_api'),
]
