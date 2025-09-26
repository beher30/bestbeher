#!/usr/bin/env python
"""
Database connection test script
Tests both development (SQLite) and production (PostgreSQL) configurations
"""
import os
import sys
import django
from django.conf import settings

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.db import connection
from django.core.management.color import make_style

style = make_style()

def test_database_connection():
    """Test database connection and display configuration"""
    print(style.SUCCESS("🔍 Testing Database Configuration"))
    print("-" * 50)
    
    # Display current environment
    debug_mode = settings.DEBUG
    print(f"Debug Mode: {debug_mode}")
    print(f"Environment: {'Development' if debug_mode else 'Production'}")
    
    # Display database configuration
    db_config = settings.DATABASES['default']
    print(f"Database Engine: {db_config['ENGINE']}")
    
    if 'postgresql' in db_config['ENGINE']:
        print(f"Database Name: {db_config.get('NAME', 'N/A')}")
        print(f"Database User: {db_config.get('USER', 'N/A')}")
        print(f"Database Host: {db_config.get('HOST', 'N/A')}")
        print(f"Database Port: {db_config.get('PORT', 'N/A')}")
        print(f"SSL Mode: {db_config.get('OPTIONS', {}).get('sslmode', 'N/A')}")
    else:
        print(f"Database File: {db_config.get('NAME', 'N/A')}")
    
    print("-" * 50)
    
    try:
        # Test connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
        if result[0] == 1:
            print(style.SUCCESS("✅ Database connection successful!"))
            
            # Get database info safely
            try:
                if 'postgresql' in db_config['ENGINE']:
                    cursor.execute("SELECT version()")
                    version_info = cursor.fetchone()[0]
                    print(f"Database Version: {version_info.split()[0]} {version_info.split()[1]}")
                elif 'sqlite' in db_config['ENGINE']:
                    cursor.execute("SELECT sqlite_version()")
                    version_info = cursor.fetchone()[0]
                    print(f"SQLite Version: {version_info}")
            except Exception:
                print("Database Version: Available")
        else:
            print(style.ERROR("❌ Database connection test failed"))
            
    except Exception as e:
        print(style.ERROR(f"❌ Database connection error: {str(e)}"))
        if debug_mode:
            print(style.WARNING("Note: This is expected in development without PostgreSQL server"))
        else:
            print(style.ERROR("This needs to be fixed before production deployment"))

if __name__ == '__main__':
    test_database_connection()