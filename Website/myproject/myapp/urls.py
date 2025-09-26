# myapp/urls.py
from django.urls import path
from . import views
from .views import add_video_form
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),  
    path('terms/', views.terms_and_conditions, name='terms'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    
    # Course and Video URLs
    path('courses/', views.course_list, name='course_list'),
    path('courses/<int:course_id>/', views.course_detail, name='course_detail'),
    path('videos/<int:video_id>/', views.video_player, name='video_player'),
    path('videos/', views.videos_index, name='videos_index'),
    path('videos/<int:video_id>/progress/', views.update_video_progress, name='video_progress'),
    path('upgrade-membership/', views.upgrade_membership, name='upgrade_membership'),
    path('submit-payment-proof/', views.submit_payment_proof, name='submit_payment_proof'),
    
    # Legacy video streaming URLs (keeping for backward compatibility)
    path('video_streaming/welcome/', views.welcome_view, name='welcome'),
    path('video_streaming/', views.video_streaming_index, name='video_streaming_index'),
    path('video_streaming/index/', views.video_streaming_index, name='video_streaming_index_path'),
    path('video_streaming/course/', views.video_streaming_course, name='video_streaming_course'),
    path('video_streaming/list/', views.video_list, name='video_list'),
    path('video_streaming/list/<int:video_id>/', views.video_list, name='video_list_detail'),
    path('video_streaming/progress/<int:video_id>/', views.update_video_progress, name='update_video_progress_legacy'),
    path('video_streaming/<str:video_name>/', views.video_view, name='video_view'),
    path('payment-required/', views.payment_required, name='payment_required'),
    path('free-course/', views.free_course, name='free_course'),  # Added free course URL
    path('free-videos/<int:video_id>/', views.free_video_player, name='free_video_player'),  # New route for free videos
    
    # Admin URLs - Changed from admin/dashboard to dashboard to avoid conflict
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/stats/<str:timeframe>/', views.dashboard_stats, name='dashboard_stats'),
    path('dashboard/events/', views.dashboard_events, name='dashboard_events'),
    path('dashboard/users/', views.user_management, name='user_management'),
    path('dashboard/users/<int:user_id>/membership/', views.update_membership, name='update_membership'),
    path('dashboard/users/<int:user_id>/', views.user_details, name='user_details'),
    path('dashboard/users/<int:user_id>/activate/', views.activate_user, name='activate_user'),
    path('dashboard/users/<int:user_id>/deactivate/', views.deactivate_user, name='deactivate_user'),
    
    # Payment proof handling
    path('dashboard/payment-proofs/<int:proof_id>/<str:action>/', views.handle_payment_proof, name='handle_payment_proof'),
    path('dashboard/process-payment-proof/<int:proof_id>/', views.process_payment_proof, name='process_payment_proof'),
    
    # Video management
    path('dashboard/videos/', views.video_management, name='video_management'),
    path('dashboard/videos/add/', views.add_video_form, name='add_video_form'),  # Added URL for add video form
    path('dashboard/videos/bulk-upload/', views.bulk_video_upload, name='bulk_video_upload'),
    path('dashboard/videos/<int:video_id>/', views.get_video, name='get_video'),
    path('dashboard/videos/<int:video_id>/toggle/', views.toggle_video_status, name='toggle_video_status'),
    path('dashboard/videos/<int:video_id>/delete/', views.delete_video, name='delete_video'),
    
    # Other dashboard sections
    path('dashboard/payments/', views.payment_management, name='payment_management'),
    path('dashboard/reports/', views.reports, name='reports'),
    path('dashboard/settings/', views.admin_settings, name='admin_settings'),
    path('dashboard/profile/', views.admin_profile, name='admin_profile'),
    path('dashboard/profile/update/', views.update_profile, name='update_profile'),  # Added update profile endpoint
    path('dashboard/audit-logs/', views.audit_logs, name='audit_logs'),
    
    # Video streaming and analytics
    path('videos/<int:video_id>/analytics/', views.track_video_analytics, name='track_video_analytics'),
    
    # MEGA Video management
    path('dashboard/mega-videos/<int:video_id>/delete/', views.delete_mega_video, name='delete_mega_video'),
    
    # Google Drive management
    path('dashboard/folders/', views.drive_folder_management, name='drive_folder_management'),
    path('dashboard/folders/<int:folder_id>/update-tier/', views.update_folder_tier, name='update_folder_tier'),
    path('dashboard/folders/<int:folder_id>/delete/', views.delete_folder, name='delete_folder'),
    path('dashboard/folders/<int:folder_id>/sync/', views.sync_folder, name='sync_folder'),
    path('dashboard/folders/add/', views.add_folder, name='add_folder'),
    path('folders/<int:folder_id>/', views.folder_detail, name='folder_detail'),
    path('dashboard/folders/list/', views.folder_videos_list, name='folder_videos_list'),
    path('dashboard/folders/<int:folder_id>/videos/', views.folder_videos_detail, name='folder_videos_detail'),
    path('dashboard/folders/<int:folder_id>/access/', views.manage_folder_access, name='manage_folder_access'),
    path('dashboard/folders/events/', views.folder_events, name='folder_events'),
    path('api/folders/<int:folder_id>/videos/', views.get_folder_videos, name='get_folder_videos'),
    
    # Video streaming
    path('videos/<int:video_id>/stream/', views.video_streaming, name='video_streaming'),
    path('videos/<int:video_id>/progress/', views.update_video_progress, name='update_video_progress'),
    path('membership/', views.membership_page, name='membership_page'),
    path('membership/upgrade/', views.upgrade_membership, name='upgrade_membership'),
    path('membership/upload-proof/<int:payment_id>/', views.upload_payment_proof, name='upload_payment_proof'),
    path('upload-payment-proof/', views.upload_payment_proof, name='upload_payment_proof'),
    path('membership/upgrade/', views.membership_upgrade, name='membership_upgrade'),
]
