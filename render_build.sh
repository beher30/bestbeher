#!/bin/bash

# Exit on error
set -e

# Print each command
set -x

# Create a requirements.txt file in the current directory
echo "Creating requirements.txt..."
echo "Django>=5.1.6" > requirements.txt
echo "gunicorn==21.2.0" >> requirements.txt
echo "psycopg2-binary==2.9.9" >> requirements.txt
echo "whitenoise==6.6.0" >> requirements.txt
echo "asgiref==3.8.1" >> requirements.txt
echo "sqlparse==0.4.4" >> requirements.txt
echo "pytz==2023.3" >> requirements.txt
echo "django-environ==0.11.2" >> requirements.txt
echo "python-dotenv==1.0.0" >> requirements.txt
echo "django-cors-headers==4.3.1" >> requirements.txt
echo "Pillow==10.0.0" >> requirements.txt

# Install Python and build dependencies
python -m pip install --upgrade pip setuptools wheel

# Install from requirements.txt
pip install -r requirements.txt

# Install the package in development mode
pip install -e .

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate
# Exit on error
set -e

echo "=== Starting Build Process ==="

# Print Python version
python --version

# Upgrade pip and setuptools
python -m pip install --upgrade pip setuptools wheel

# Create a minimal requirements.txt if it doesn't exist
if [ ! -f requirements.txt ]; then
    echo "Creating minimal requirements.txt..."
    echo "-e ." > requirements.txt
fi

# Install dependencies from pyproject.toml
if [ -f pyproject.toml ]; then
    echo "Installing from pyproject.toml..."
    pip install -e .
else
    echo "pyproject.toml not found, using requirements.txt..."
    pip install -r requirements.txt
fi

# Install gunicorn explicitly
pip install gunicorn==21.2.0

# Install any additional requirements if they exist
if [ -f requirements.txt ]; then
    echo "Installing additional requirements..."
    pip install -r requirements.txt
fi

# Run database migrations
echo "Running migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "=== Build Process Complete ==="
pip list
