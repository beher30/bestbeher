#!/bin/bash
set -ex

# Debug information
echo "=== Start Script ==="
echo "Current directory: $(pwd)"

# Activate the virtual environment
echo -e "\n=== Activating virtual environment ==="
source /opt/render/project/src/.venv/bin/activate

# Set environment variables
export PYTHONPATH="/opt/render/project/src/Website/myproject:$PYTHONPATH"
export DJANGO_SETTINGS_MODULE="myproject.settings"
export PYTHONUNBUFFERED=1

# Show environment information
echo -e "\n=== Environment Information ==="
python --version
pip --version
which python
which pip
env | sort

# Navigate to the project directory
echo -e "\n=== Changing to project directory ==="
cd /opt/render/project/src/Website/myproject
echo "Current directory: $(pwd)"
ls -la

# Verify Django installation
echo -e "\n=== Verifying Django installation ==="
python -c "import django; print(f'Django version: {django.__version__}')"

# Run database migrations
echo -e "\n=== Running database migrations ==="
python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo -e "\n=== Checking for superuser ==="
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print('No superuser found. Creating one...')
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created successfully!')
else:
    print('Superuser already exists.')
"

# Collect static files
echo -e "\n=== Collecting static files ==="
python manage.py collectstatic --noinput --clear

# Start Gunicorn
echo -e "\n=== Starting Gunicorn ==="
exec gunicorn \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 3 \
    --worker-class gthread \
    --threads 2 \
    --log-level=info \
    --log-file=- \
    --access-logfile=- \
    --error-logfile=- \
    --timeout 120 \
    --max-requests 5000 \
    --max-requests-jitter 500 \
    myproject.wsgi:application

# Run migrations
echo "\n=== Running migrations ==="
python manage.py migrate --noinput

# Collect static files
echo "\n=== Collecting static files ==="
python manage.py collectstatic --noinput --clear

# Start Gunicorn
echo "\n=== Starting Gunicorn ==="
echo "Using PORT: $PORT"

# Ensure we have the correct Python path
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Debug: Show Python path and Gunicorn location
echo "Python path: $PYTHONPATH"
which gunicorn || echo "Gunicorn not found in PATH"

# Start Gunicorn with the correct module path
exec gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --log-level=debug --chdir .
