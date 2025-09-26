from setuptools import setup, find_packages

# Core dependencies
install_requires = [
    # Core Django
    'mega.py==1.0.8',
    'tenacity==5.1.5',
    'ffmpeg-python==0.2.0',
    'Django>=5.1.6',
    'asgiref==3.8.1',
    'sqlparse==0.4.4',
    'pytz==2023.3',
    
    # Database
    'psycopg2-binary==2.9.9',
    
    # Static files
    'whitenoise==6.6.0',
    
    # Environment
    'django-environ==0.11.2',
    'python-dotenv==1.0.0',
    
    # CORS headers
    'django-cors-headers==4.3.1',
    
    # Storage & Media
    'django-storages==1.14.2',
    'boto3==1.34.28',
    'Pillow==10.0.0',
    
    # Production
    'gunicorn==21.2.0',
    'dj-database-url==2.1.0',
    
    # Security
    'django-csp==3.7',
    'django-ratelimit==4.1.0',
    
    # Required Python packages
    'certifi>=2023.7.22',
    'charset-normalizer>=3.2.0,<4.0.0',
    'idna>=3.4',
    'requests>=2.31.0',
    'urllib3>=2.0.4',
    'pathlib==1.0.1',
    'six>=1.9.0',
    'future>=0.18.3',
]

setup(
    name="beherbest",
    version="1.0.0",
    packages=find_packages(),
    install_requires=install_requires,
    python_requires='>=3.10',
    author="Your Name",
    author_email="your.email@example.com",
    description="BeHerBest - A Django-based web application",
    long_description=open('README.md', 'r', encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/beher30/Beherbest",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Framework :: Django :: 4.2",
    ],
    include_package_data=True,
    zip_safe=False,
)
