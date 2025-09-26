from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import os
import json
import logging
from typing import Optional, Dict, Any
from googleapiclient.errors import HttpError
from cryptography.fernet import Fernet
import base64
import time

logger = logging.getLogger(__name__)

# Placeholder for MEGA integration service logic
# Use mega.py or similar library for MEGA operations

    """Service class for Google Drive operations"""
    
    def __init__(self):
        try:
            self.credentials = self._get_credentials()
            self.service = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
            logger.info("Successfully initialized Google Drive service")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {str(e)}")
            raise
    
    def _get_credentials(self):
        """Get service account credentials"""
        try:
            credentials_path = settings.GOOGLE_DRIVE_CREDENTIALS_PATH
            if not os.path.exists(credentials_path):
                raise Exception(f"Service account credentials file not found at {credentials_path}")
            
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=settings.GOOGLE_DRIVE_SCOPES
            )
            return credentials
        except Exception as e:
            logger.error(f"Error getting service account credentials: {str(e)}")
            raise Exception("Failed to initialize Google Drive service")
    
    def generate_signed_url(self, file_id, user):
        """Generate a streaming URL for a video"""
        try:
            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, webContentLink'
            ).execute()

            if not file.get('webContentLink'):
                # Generate a temporary download URL
                request = self.service.files().get_media(fileId=file_id)
                download_url = request.uri

                # Add authorization header to URL
                auth_header = f"Bearer {self.credentials.token}"
                stream_url = f"{download_url}&access_token={self.credentials.token}"

                return stream_url
            else:
                # Use the webContentLink but modify it for streaming
                stream_url = file['webContentLink'].replace('&export=download', '')
                return stream_url

        except Exception as e:
            logger.error(f"Error generating signed URL: {str(e)}")
            raise Exception("Unable to generate streaming URL")
    
    def generate_secure_url(self, file_id, user, session_key):
        """Generate a secure streaming URL with encryption"""
        try:
            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, webContentLink'
            ).execute()

            # Create a secure token with user info and timestamp
            token_data = {
                'file_id': file_id,
                'user_id': user.id,
                'email': user.email,
                'timestamp': int(time.time()),
                'session_key': session_key
            }

            # Encrypt the token
            token = base64.urlsafe_b64encode(
                self.cipher_suite.encrypt(json.dumps(token_data).encode())
            ).decode()

            # Generate the streaming URL
            if file.get('webContentLink'):
                base_url = file['webContentLink'].replace('&export=download', '')
            else:
                request = self.service.files().get_media(fileId=file_id)
                base_url = request.uri

            # Append the encrypted token
            stream_url = f"{base_url}&token={token}"
            return stream_url

        except Exception as e:
            logger.error(f"Error generating secure URL: {str(e)}")
            raise Exception("Unable to generate streaming URL")
    
    def extract_folder_id(self, folder_id_or_url: str) -> str:
        """Extract folder ID from URL or return the ID if already clean"""
        if not folder_id_or_url:
            raise ValueError("Folder ID cannot be empty")
            
        # If it's already just an ID, return it
        if not any(marker in folder_id_or_url for marker in ['drive.google.com', '/']):
            return folder_id_or_url
            
        # Extract ID from URL
        try:
            # Handle different URL formats
            if 'folders/' in folder_id_or_url:
                return folder_id_or_url.split('folders/')[-1].split('?')[0].split('/')[0]
            elif 'id=' in folder_id_or_url:
                return folder_id_or_url.split('id=')[-1].split('&')[0]
            else:
                raise ValueError("Invalid Google Drive folder URL format")
        except Exception as e:
            logger.error(f"Error extracting folder ID from {folder_id_or_url}: {str(e)}")
            raise ValueError("Could not extract folder ID from URL")
    
    def process_video(self, video_data: Dict, folder_id: str) -> None:
        """Process a single video from Google Drive with improved metadata handling"""
        try:
            # Import models here to avoid circular import
            from django.apps import apps
            GoogleDriveFolder = apps.get_model('myapp', 'GoogleDriveFolder')
            GoogleDriveVideo = apps.get_model('myapp', 'GoogleDriveVideo')
            
            # Get the GoogleDriveFolder instance first
            folder = GoogleDriveFolder.objects.get(folder_id=folder_id)
            
            # Get video metadata with detailed error handling
            video_metadata = video_data.get('videoMediaMetadata', {})
            duration_millis = None
            
            # Handle duration conversion with detailed error logging
            try:
                raw_duration = video_metadata.get('durationMillis')
                if raw_duration:
                    if isinstance(raw_duration, str):
                        duration_millis = int(raw_duration)
                    elif isinstance(raw_duration, (int, float)):
                        duration_millis = int(raw_duration)
                    else:
                        logger.warning(f"Unexpected duration type for video {video_data.get('id')}: {type(raw_duration)}")
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting duration for video {video_data.get('id')}: {str(e)}")
            
            # Get additional metadata with fallbacks
            title = video_data.get('name', '').strip() or 'Untitled Video'
            description = video_data.get('description', '').strip() or ''
            thumbnail_url = video_data.get('thumbnailLink', '')
            mime_type = video_data.get('mimeType', '')
            
            # Verify mime type is video
            if not mime_type.startswith('video/'):
                logger.warning(f"Non-video mime type detected: {mime_type} for file {video_data.get('id')}")
            
            # Get or create video record with improved defaults
            video, created = GoogleDriveVideo.objects.update_or_create(
                drive_file_id=video_data['id'],
                folder=folder,
                defaults={
                    'title': title,
                    'description': description,
                    'thumbnail_url': thumbnail_url,
                    'duration_ms': duration_millis,
                    'mime_type': mime_type,
                    'last_modified': video_data.get('modifiedTime'),
                    'size_bytes': video_data.get('size'),
                    'processing_status': 'completed',
                    'is_active': True
                }
            )
            
            # Log success
            action = 'Created' if created else 'Updated'
            logger.info(f"{action} video record: {video.title} (ID: {video.drive_file_id})")
            
            return video
            
        except Exception as e:
            error_msg = f"Error processing video {video_data.get('name', 'unknown')}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    @staticmethod
    def format_duration(duration_millis: Optional[int]) -> str:
        """Format duration from milliseconds to human-readable string"""
        if not duration_millis:
            return "Unknown"
    
        try:
            # Convert duration_millis to int if it's a string
            if isinstance(duration_millis, str):
                duration_millis = int(duration_millis)
            
            total_seconds = int(duration_millis / 1000)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes}:{seconds:02d}"
        except (ValueError, TypeError):
            logger.warning(f"Invalid duration value: {duration_millis}")
            return "Unknown"
    
    def sync_folder(self, folder_id: str) -> Dict[str, Any]:
        """
        Sync folder contents with database, handling pagination and maintaining state.
        Returns a dictionary with sync results.
        """
        try:
            start_time = time.time()
            page_token = None
            all_files = []
            processed_count = 0
            updated_count = 0
            deleted_count = 0
            errors = []

            # Get existing video IDs in database for this folder
            from ..models import GoogleDriveVideo, GoogleDriveFolder
            folder = GoogleDriveFolder.objects.get(folder_id=folder_id)
            existing_video_ids = set(GoogleDriveVideo.objects.filter(
                folder=folder
            ).values_list('drive_file_id', flat=True))
            
            # Track which files we find in Drive
            found_video_ids = set()

            while True:
                try:
                    # List all video files in the folder with pagination
                    results = self.service.files().list(
                        q=f"'{folder_id}' in parents and mimeType contains 'video/'",
                        spaces='drive',
                        fields='nextPageToken, files(id, name, mimeType, thumbnailLink, videoMediaMetadata, description, modifiedTime)',
                        pageToken=page_token,
                        pageSize=100,
                        orderBy='name'
                    ).execute()

                    items = results.get('files', [])
                    
                    # Process each video in the current page
                    for item in items:
                        try:
                            video_id = item['id']
                            found_video_ids.add(video_id)
                            
                            # Get video metadata
                            video_metadata = item.get('videoMediaMetadata', {})
                            duration_millis = video_metadata.get('durationMillis')
                            if isinstance(duration_millis, str):
                                duration_millis = int(duration_millis)
                            
                            # Update or create video record
                            video, created = GoogleDriveVideo.objects.update_or_create(
                                drive_file_id=video_id,
                                folder=folder,
                                defaults={
                                    'title': item.get('name', ''),
                                    'description': item.get('description', ''),
                                    'thumbnail_url': item.get('thumbnailLink', ''),
                                    'duration_ms': duration_millis,
                                    'last_modified': item.get('modifiedTime'),
                                    'mime_type': item.get('mimeType', '')
                                }
                            )
                            
                            if created:
                                processed_count += 1
                            else:
                                updated_count += 1
                                
                        except Exception as video_error:
                            error_msg = f"Error processing video {item.get('name', 'unknown')}: {str(video_error)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue

                    # Get the next page token
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break

                except HttpError as error:
                    error_msg = f"Error fetching videos page: {str(error)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    break

            # Handle deleted videos
            deleted_videos = existing_video_ids - found_video_ids
            if deleted_videos:
                # Mark videos as deleted instead of actually deleting them
                deleted_count = GoogleDriveVideo.objects.filter(
                    drive_file_id__in=deleted_videos
                ).update(
                    is_deleted=True,
                    deleted_at=timezone.now()
                )

            # Update folder metadata
            folder.last_synced = timezone.now()
            folder.video_count = len(found_video_ids)
            folder.save()

            # Calculate sync duration
            sync_duration = time.time() - start_time

            # Create detailed sync report
            sync_report = {
                'status': 'success' if not errors else 'partial_success',
                'total_videos': len(found_video_ids),
                'new_videos': processed_count,
                'updated_videos': updated_count,
                'deleted_videos': deleted_count,
                'errors': errors,
                'sync_duration': sync_duration,
                'timestamp': timezone.now().isoformat()
            }

            # Log sync results
            logger.info(f"Folder sync completed for {folder_id}: {json.dumps(sync_report)}")

            return sync_report

        except Exception as e:
            error_msg = f"Error syncing folder {folder_id}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_video_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get video metadata from Google Drive"""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id,name,mimeType,size,modifiedTime,webContentLink'
            ).execute()
            
            return {
                'file_id': file.get('id'),
                'name': file.get('name'),
                'mime_type': file.get('mimeType'),
                'size': file.get('size'),
                'last_modified': file.get('modifiedTime'),
                'web_link': file.get('webContentLink')
            }
            
        except Exception as e:
            logger.error(f"Error getting video metadata for {file_id}: {str(e)}")
            raise
    
    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new folder in Google Drive"""
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            file = self.service.files().create(
                body=file_metadata,
                fields='id,name,webViewLink'
            ).execute()
            
            return {
                'id': file.get('id'),
                'name': file.get('name'),
                'web_link': file.get('webViewLink')
            }
            
        except Exception as e:
            logger.error(f"Error creating folder {name}: {str(e)}")
            raise

    def count_folder_videos(self, folder_id):
        try:
            # Get video files from folder
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType contains 'video/'",
                fields="files(id, name)"
            ).execute()
            return len(results.get('files', []))
        except Exception as e:
            logger.error(f"Error counting videos in folder {folder_id}: {str(e)}")
            return 0

    def create_video_record(self, file_data, folder):
        # Import the model here instead
        from ..models import GoogleDriveVideo
        
        video = GoogleDriveVideo.objects.create(
            title=file_data['name'],
            drive_file_id=file_data['id'],
            folder=folder,
            # ... other fields ...
        )
        return video

    def list_folder_videos(self, folder_id):
        """List all video files in a folder"""
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and mimeType contains 'video/'",
                spaces='drive',
                fields='files(id, name, mimeType, thumbnailLink, videoMediaMetadata, description)',
                pageSize=1000
            ).execute()
            
            videos = []
            for item in results.get('files', []):
                video_data = {
                    'id': item['id'],
                    'name': item['name'],
                    'thumbnail_url': item.get('thumbnailLink', ''),
                    'duration_ms': item.get('videoMediaMetadata', {}).get('durationMillis'),
                    'description': item.get('description', '')
                }
                videos.append(video_data)
            
            return videos
            
        except Exception as e:
            logger.error(f"Error listing folder videos: {str(e)}")
            raise Exception(f"Failed to list videos: {str(e)}")

    def get_direct_stream_url(self, file_id):
        """Get direct streaming URL for a video file"""
        try:
            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, webContentLink'
            ).execute()

            # Generate a direct streaming URL
            access_token = self.credentials.token
            base_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            stream_url = f"{base_url}&access_token={access_token}"
            
            return stream_url

        except Exception as e:
            logger.error(f"Error getting stream URL: {str(e)}")
            raise Exception("Unable to generate streaming URL")

    def get_secure_stream_url(self, file_id, user):
        """Generate secure streaming URL with user watermark and caching"""
        cache_key = f'stream_url_{file_id}_{user.id}'
        cached_url = cache.get(cache_key)
        
        if cached_url:
            return cached_url
            
        try:
            # Verify file exists and user has access
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, webContentLink, size, md5Checksum'
            ).execute()

            if not file:
                raise Exception("Video file not found")

            if 'video' not in file.get('mimeType', ''):
                raise Exception("File is not a video")

            # Generate secure token with user info (no expiration)
            token_data = {
                'file_id': file_id,
                'user_id': user.id,
                'email': user.email,
                'checksum': file.get('md5Checksum', '')
            }

            # Create secure token
            token = base64.urlsafe_b64encode(
                json.dumps(token_data).encode()
            ).decode()

            # Ensure credentials are fresh
            if self.credentials.expired:
                self.credentials.refresh(Request())

            # Generate base streaming URL
            base_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            
            # Add authorization and user tracking
            final_url = f"{base_url}&access_token={self.credentials.token}&user_token={token}"

            # Cache the URL for 12 hours (increased from 30 minutes since we removed expiration)
            cache.set(cache_key, final_url, timeout=43200)

            return final_url

        except Exception as e:
            logger.error(f"Error generating secure stream URL for file {file_id}: {str(e)}")
            raise Exception(f"Unable to generate streaming URL: {str(e)}")

    def verify_video_access(self, file_id: str, user) -> bool:
        """Verify if user has access to the video"""
        try:
            # Get video metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='id, parents'
            ).execute()

            if not file:
                return False

            # Get folder ID
            folder_id = file.get('parents', [None])[0]
            if not folder_id:
                return False

            # Import models here to avoid circular import
            from ..models import GoogleDriveFolder
            
            try:
                folder = GoogleDriveFolder.objects.get(folder_id=folder_id)
                # Check user's membership tier against folder's required tier
                return folder.can_access(user)
            except GoogleDriveFolder.DoesNotExist:
                return False

        except Exception as e:
            logger.error(f"Error verifying video access for file {file_id}: {str(e)}")
            return False

    def get_video_stream(self, file_id: str, user, range_header: Optional[str] = None) -> Dict[str, Any]:
        """Get video stream with support for range requests"""
        try:
            # Verify access first
            if not self.verify_video_access(file_id, user):
                raise Exception("Access denied")

            # Get file metadata
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size'
            ).execute()

            if not file:
                raise Exception("Video not found")

            # Parse range header
            start = 0
            end = int(file.get('size', 0)) - 1
            content_length = end + 1

            if range_header:
                try:
                    ranges = range_header.replace('bytes=', '').split('-')
                    start = int(ranges[0])
                    if ranges[1]:
                        end = int(ranges[1])
                except (IndexError, ValueError):
                    pass

            # Create media request
            request = self.service.files().get_media(
                fileId=file_id
            )
            
            # Add range header if needed
            if range_header:
                request.headers['Range'] = f'bytes={start}-{end}'

            return {
                'request': request,
                'mime_type': file.get('mimeType', 'video/mp4'),
                'size': content_length,
                'start': start,
                'end': end
            }

        except Exception as e:
            logger.error(f"Error getting video stream for file {file_id}: {str(e)}")
            raise 