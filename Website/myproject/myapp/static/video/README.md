# Video Files Directory

This directory contains video files for the website.

## Note for Production Deployment

Large video files (like `presentation.mp4`) are excluded from git to avoid push timeouts.

For production deployment:
1. Upload video files directly to your server
2. Or use external video hosting (YouTube, Vimeo, etc.)
3. Or use cloud storage (AWS S3, Cloudinary, etc.)

## Current Files

- `presentation.mp4` - Main presentation video (14.5MB) - Upload separately to production

## Video File Locations

The website expects video files at:
- `/static/video/presentation.mp4` - Main hero video
- Add other video files as needed

## For Local Development

If you need the video file for local testing:
1. Obtain the `presentation.mp4` file
2. Place it in this directory
3. The file will be ignored by git (see .gitignore)