#!/bin/bash
set -ex

# Debug information
echo "=== Build Script ==="
echo "Current directory: $(pwd)"

# Show environment
echo -e "\n=== Environment ==="
printenv

# Check Python version
echo -e "\n=== Python version ==="
python --version

# Create and activate virtual environment
echo -e "\n=== Setting up Python environment ==="
python -m venv /opt/render/project/src/.venv
source /opt/render/project/src/.venv/bin/activate

# Upgrade pip and setuptools
echo -e "\n=== Upgrading pip and setuptools ==="
python -m pip install --upgrade pip setuptools wheel

# Install dependencies
echo -e "\n=== Installing dependencies ==="
pip install -r requirements.txt

# Verify installations
echo -e "\n=== Verifying installations ==="
python -c "import django; print(f'Django version: {django.__version__}')"
python -c "import gunicorn; print(f'Gunicorn version: {gunicorn.__version__}')"

# Navigate to the project directory
cd /opt/render/project/src/Website/myproject

# Install project in development mode
echo -e "\n=== Installing project in development mode ==="
pip install -e .

# Run database migrations
echo -e "\n=== Running database migrations ==="
python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo -e "\n=== Creating superuser if it doesn't exist ==="
cat <<EOF | python manage.py shell
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created successfully!')
else:
    print('Superuser already exists.')
EOF

# Collect static files
echo -e "\n=== Collecting static files ==="
python manage.py collectstatic --noinput --clear

# Show installed packages for debugging
echo -e "\n=== Installed packages ==="
pip list

# Show directory structure
echo -e "\n=== Current directory structure ==="
ls -la

echo -e "\n=== Build completed successfully! ==="

# Final verification
echo -e "\n=== Final verification ==="
python -c "import django; print(f'Django version: {django.__version__}')"
pip list
