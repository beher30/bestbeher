from django.urls import path
from . import views_api

urlpatterns = [
    path('api/video-progress/<int:video_id>/', views_api.video_progress_api, name='video_progress_api'),
    path('api/mega-videos/<int:video_id>/delete/', views_api.delete_mega_video_api, name='delete_mega_video_api'),
]
