from django.urls import path
from . import views_mega

urlpatterns = [
    # MEGA video management
    path('dashboard/mega-videos/', views_mega.mega_video_management, name='mega_video_management'),
    path('dashboard/mega-videos/add/', views_mega.add_mega_video, name='add_mega_video'),
    path('dashboard/mega-videos/<int:video_id>/edit/', views_mega.edit_mega_video, name='edit_mega_video'),
    path('dashboard/mega-videos/<int:video_id>/delete/', views_mega.delete_mega_video, name='delete_mega_video'),
    
    # MEGA video playback
    path('videos/mega/<int:video_id>/', views_mega.play_mega_video, name='play_mega_video'),
    path('videos/mega/stream/', views_mega.stream_mega_video, name='stream_mega_video'),
    path('api/mega-videos/<int:video_id>/progress/', views_mega.update_mega_video_progress, name='update_mega_video_progress'),
    path('embed/mega/', views_mega.mega_video_embed, name='mega_video_embed'),
]
