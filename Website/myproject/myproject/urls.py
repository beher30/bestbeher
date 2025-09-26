from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from myapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('myapp.urls')),
    path('', include('myapp.urls_video')),
    path('', include('myapp.urls_api')),
    path('', include('myapp.urls_mega')),  # Include MEGA URLs
    path('videos/<int:video_id>/', views.video_player, name='video_player'),
    path('free-videos/<int:video_id>/', views.free_video_player, name='free_video_player'),
    path('video-streaming/course/', views.video_streaming_course, name='video_streaming_course'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Add static and media file serving for development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)