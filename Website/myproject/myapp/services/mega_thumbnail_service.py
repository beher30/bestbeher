import os
import tempfile
import subprocess
import logging
import requests
from django.core.files import File
from django.conf import settings
import ffmpeg
import json
import base64

logger = logging.getLogger(__name__)

def download_mega_file(mega_link: str) -> str:
    """
    Download a file from MEGA using direct download
    Returns the path to the downloaded file
    """
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, 'temp_video.mp4')
        
        # Extract file ID and key from the MEGA link
        if '/file/' in mega_link and '#' in mega_link:
            file_id = mega_link.split('/file/')[1].split('#')[0]
            key = mega_link.split('#')[1]
            
            # Construct direct download URL with key
            download_url = f"https://mega.nz/file/{file_id}/download#{key}"
            
            # Download the file
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return temp_file
        else:
            raise ValueError("Invalid MEGA link format")
            
    except Exception as e:
        logger.error(f"Error downloading MEGA file: {str(e)}")
        raise

def generate_thumbnail(video_path: str) -> str:
    """
    Generate a thumbnail from a video file using ffmpeg
    Returns the path to the generated thumbnail
    """
    try:
        # Create a temporary directory for the thumbnail
        temp_dir = tempfile.mkdtemp()
        thumbnail_path = os.path.join(temp_dir, 'thumbnail.jpg')
        
        # Use ffmpeg-python to extract a frame at 2 seconds
        stream = ffmpeg.input(video_path, ss='00:00:02')
        stream = ffmpeg.output(stream, thumbnail_path, vframes=1, q=2)
        ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
        
        return thumbnail_path
        
    except Exception as e:
        logger.error(f"Error generating thumbnail: {str(e)}")
        raise

def cleanup_temp_files(*file_paths):
    """Clean up temporary files and directories"""
    for path in file_paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                # Remove all files in directory first
                for root, dirs, files in os.walk(path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(path)
        except Exception as e:
            logger.error(f"Error cleaning up temporary file {path}: {str(e)}")

def generate_video_thumbnail(mega_link: str) -> str:
    """
    Main function to generate a thumbnail from a MEGA video link
    Returns the path to the generated thumbnail
    """
    video_path = None
    thumbnail_path = None
    temp_dirs = []
    
    try:
        # Download the video
        video_path = download_mega_file(mega_link)
        temp_dirs.append(os.path.dirname(video_path))
        
        # Generate thumbnail
        thumbnail_path = generate_thumbnail(video_path)
        temp_dirs.append(os.path.dirname(thumbnail_path))
        
        return thumbnail_path
        
    except Exception as e:
        logger.error(f"Error in generate_video_thumbnail: {str(e)}")
        raise
        
    finally:
        # Clean up all temporary files and directories
        if video_path:
            cleanup_temp_files(video_path)
        for temp_dir in temp_dirs:
            cleanup_temp_files(temp_dir) 