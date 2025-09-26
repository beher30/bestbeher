import os
import json
import logging
import re
import time
import uuid
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from cryptography.fernet import Fernet
import base64
import requests

logger = logging.getLogger(__name__)

class MegaService:
    """Service class for MEGA operations"""
    
    def __init__(self):
        self.encryption_key = settings.SECRET_KEY[:32].encode()
        self.fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key.ljust(32)[:32]))
        logger.info("Successfully initialized MEGA service")
    
    def extract_mega_id(self, mega_url: str) -> str:
        """Extract MEGA file ID from URL"""
        # MEGA URLs are typically in format: https://mega.nz/file/{file_id}#{key}
        # or https://mega.nz/folder/{folder_id}#{key}
        
        if not mega_url:
            return None
            
        # Extract file/folder ID
        pattern = r'mega\.nz\/(?:file|folder)\/([a-zA-Z0-9_-]+)(?:#([a-zA-Z0-9_-]+))?'
        match = re.search(pattern, mega_url)
        
        if match:
            file_id = match.group(1)
            return file_id
        return None
    
    def extract_mega_key(self, mega_url: str) -> str:
        """Extract decryption key from MEGA URL"""
        if not mega_url:
            return None
            
        pattern = r'mega\.nz\/(?:file|folder)\/[a-zA-Z0-9_-]+#([a-zA-Z0-9_-]+)'
        match = re.search(pattern, mega_url)
        
        if match:
            key = match.group(1)
            return key
        return None
    
    def is_folder_link(self, mega_url: str) -> bool:
        """Check if the MEGA URL is a folder link"""
        if not mega_url:
            return False
            
        return 'mega.nz/folder/' in mega_url
    
    def is_file_link(self, mega_url: str) -> bool:
        """Check if the MEGA URL is a file link"""
        if not mega_url:
            return False
            
        # Support both old and new MEGA URL formats
        # Old format: https://mega.nz/#!file_id!file_key
        # New format: https://mega.nz/file/file_id#file_key
        
        # Check for new format
        if 'mega.nz/file/' in mega_url:
            # New format pattern
            pattern = r'mega\.nz\/file\/([a-zA-Z0-9_-]+)(?:#([a-zA-Z0-9_-]+))?'
            match = re.search(pattern, mega_url)
            
            # For new format, we need both file ID and key
            if match:
                return True
                
        # Check for old format
        elif 'mega.nz/#!' in mega_url:
            # Old format pattern
            pattern = r'mega\.nz\/#!([a-zA-Z0-9_-]+)!([a-zA-Z0-9_-]+)'
            match = re.search(pattern, mega_url)
            
            # For old format, we need both parts
            if match:
                return True
        
        # Also accept embed format
        elif 'mega.nz/embed/' in mega_url:
            return True
            
        return False
    
    def extract_filename_from_url(self, mega_url: str) -> str:
        """Try to extract filename from MEGA URL or metadata"""
        # This is a simplified version - in a real implementation,
        # you might need to use MEGA API to get the actual filename
        
        file_id = self.extract_mega_id(mega_url)
        if not file_id:
            return "Untitled Video"
            
        # Use the file ID as a fallback title, but truncate it
        return f"Video {file_id[:8]}"
    
    def generate_secure_url(self, mega_url: str, user, expiration_minutes=60) -> str:
        """Generate a secure URL for video playback with user-specific token"""
        if not mega_url or not user:
            return None
            
        # Create a token with user info and expiration
        timestamp = int(time.time()) + (expiration_minutes * 60)
        token_data = {
            'mega_url': mega_url,
            'user_id': user.id,
            'username': user.username,
            'timestamp': timestamp,
            'session_id': str(uuid.uuid4())
        }
        
        # Encrypt the token
        token_json = json.dumps(token_data)
        encrypted_token = self.fernet.encrypt(token_json.encode()).decode()
        
        # Return the secure token that will be used by the player
        return encrypted_token
    
    def validate_secure_token(self, token: str) -> Dict:
        """Validate a secure token and return the original data if valid"""
        if not token:
            return None
            
        try:
            # Decrypt the token
            decrypted_data = self.fernet.decrypt(token.encode()).decode()
            token_data = json.loads(decrypted_data)
            
            # Check if token is expired
            current_time = int(time.time())
            if token_data.get('timestamp', 0) < current_time:
                logger.warning(f"Token expired for user {token_data.get('username')}")
                return None
                
            return token_data
        except Exception as e:
            logger.error(f"Error validating secure token: {str(e)}")
            return None
    
    def get_video_embed_url(self, mega_url: str, user) -> str:
        """Get a secure embed URL for the MEGA video"""
        # In a real implementation, this would generate a URL that:
        # 1. Points to your application's video serving endpoint
        # 2. Includes the secure token
        # 3. Can be used with Plyr.js for playback
        
        secure_token = self.generate_secure_url(mega_url, user)
        
        # This would be the URL to your video player endpoint
        embed_url = f"/video/stream/?token={secure_token}"
        return embed_url
    
    def get_video_metadata(self, mega_url: str) -> Dict:
        """Get basic metadata for a MEGA video (simplified)"""
        # In a real implementation, you would use MEGA API to get actual metadata
        # This is a simplified version that returns placeholder data
        
        file_id = self.extract_mega_id(mega_url)
        if not file_id:
            return None
            
        # Return placeholder metadata
        return {
            'id': file_id,
            'name': self.extract_filename_from_url(mega_url),
            'size': None,  # Would be actual file size in bytes
            'duration_ms': None,  # Would be actual duration in ms
            'mime_type': 'video/mp4',  # Assumed default
            'thumbnail_url': '',  # Would be actual thumbnail URL
        }
    
    def get_streaming_url(self, mega_link: str, user) -> str:
        """
        Generate a direct streaming URL from a MEGA link.
        
        This method creates a secure token that can be used to stream the video.
        """
        try:
            # For security, we should validate the MEGA link format
            if not self.is_file_link(mega_link):
                logger.error(f"Invalid MEGA link format: {mega_link}")
                return None
            
            # Generate a secure token for this video and user
            secure_token = self.generate_secure_url(mega_link, user)
            
            # Return a URL to our video player endpoint with the secure token
            return f"/videos/mega/stream/?token={secure_token}"
            
        except Exception as e:
            logger.error(f"Error generating streaming URL: {str(e)}")
            return None
    
    def generate_watermark_data(self, user) -> Dict:
        """Generate watermark data for video playback"""
        if not user:
            return {
                'text': 'Unauthorized',
                'position': 'center',
                'opacity': '0.7'
            }
            
        # Get current time for timestamp
        current_time = timezone.now().strftime('%Y-%m-%d %H:%M')
        
        # Create watermark text with user info and timestamp
        watermark_text = f"{user.username} | {current_time}"
        
        # Add IP address if available
        try:
            import socket
            ip = socket.gethostbyname(socket.gethostname())
            watermark_text += f" | {ip}"
        except:
            pass
            
        return {
            'text': watermark_text,
            'position': 'random',  # Can be: top-left, top-right, bottom-left, bottom-right, random
            'opacity': '0.7'
        }
