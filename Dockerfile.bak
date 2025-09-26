# Use the official Python 3.10 image with a specific tag
FROM python:3.10.12-slim-bullseye

# Set environment variables
ENV PYTHONDONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=myproject.settings \
    DEBUG=True \
    PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and setuptools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy setup files first to leverage Docker cache
COPY setup.py .
COPY requirements.txt .

# Install the package and its dependencies
RUN pip install --no-cache-dir -e .

# Copy the rest of the application
COPY . .

# Set the correct working directory for the application
WORKDIR /app/Website/myproject

# Verify installation and list installed packages
RUN python -c "import django; print(f'Django version: {django.__version__}')" && \
    python -c "import sys; print('\n'.join(sys.path))" && \
    pip list

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "myproject.wsgi:application"]
