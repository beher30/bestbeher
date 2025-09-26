import re


    """Extract folder ID from Google Drive URL or return the ID if already clean"""
    # If it's already just an ID, return it
    if not any(x in url_or_id for x in ['/', '?']):
        return url_or_id
        
    # Try to extract ID from various URL formats
    patterns = [
        r'/folders/([a-zA-Z0-9-_]+)',  # /folders/ID format
        r'id=([a-zA-Z0-9-_]+)',        # id=ID format
        r'/d/([a-zA-Z0-9-_]+)',        # /d/ID format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    
    # If no patterns match, return the original string
    return url_or_id 