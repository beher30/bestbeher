#!/usr/bin/env python
"""
Development server runner that forces HTTP and eliminates HTTPS errors
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    # Force development environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    os.environ['DEBUG'] = 'True'
    os.environ['HTTPS'] = 'off'
    
    # Disable any HTTPS-related environment variables
    https_vars = ['HTTPS', 'HTTP_X_FORWARDED_PROTO', 'HTTP_X_FORWARDED_SSL']
    for var in https_vars:
        if var in os.environ:
            del os.environ[var]
    
    # Set HTTP-only variables
    os.environ['HTTP_HOST'] = '127.0.0.1:8000'
    os.environ['SERVER_NAME'] = '127.0.0.1'
    os.environ['SERVER_PORT'] = '8000'
    
    django.setup()
    
    # Start the development server with HTTP-only configuration
    print("🚀 Starting development server with HTTP-only configuration...")
    print("🌐 Access your website at: http://127.0.0.1:8000")
    print("⚠️  Do NOT use https:// - use http:// only!")
    print("-" * 60)
    
    execute_from_command_line(['manage.py', 'runserver', '127.0.0.1:8000', '--insecure'])