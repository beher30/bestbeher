# Deployment script for Django application with MEGA integration
# Based on production requirements

# Stop on first error
$ErrorActionPreference = "Stop"

# Configuration
$PROJECT_DIR = "C:\Users\NH Rich\Documents\be her\Website 1.3\website\myproject"
$PYTHON_PATH = "python"
$VENV_DIR = ".venv"
$SETTINGS_PRODUCTION = "myproject.settings_production"
$LOG_DIR = "C:\Users\NH Rich\Documents\be her\Website 1.3\logs"
$PORT = 8000

# Create log directory if it doesn't exist
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR
    Write-Host "Created log directory at $LOG_DIR" -ForegroundColor Green
}

# Navigate to project directory
Set-Location $PROJECT_DIR
Write-Host "Changed directory to $PROJECT_DIR" -ForegroundColor Green

# Activate virtual environment if it exists
if (Test-Path $VENV_DIR) {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & "$VENV_DIR\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Creating one..." -ForegroundColor Yellow
    & $PYTHON_PATH -m venv $VENV_DIR
    & "$VENV_DIR\Scripts\Activate.ps1"
    
    # Install requirements
    Write-Host "Installing requirements..." -ForegroundColor Green
    & $PYTHON_PATH -m pip install -r ..\requirements.txt
    & $PYTHON_PATH -m pip install waitress
}

# Collect static files
Write-Host "Collecting static files..." -ForegroundColor Green
$env:DJANGO_SETTINGS_MODULE = $SETTINGS_PRODUCTION
& $PYTHON_PATH manage.py collectstatic --noinput

# Run database migrations
Write-Host "Running database migrations..." -ForegroundColor Green
& $PYTHON_PATH manage.py migrate

# Check if settings_production.py exists
if (-not (Test-Path "myproject\settings_production.py")) {
    Write-Host "settings_production.py not found. Creating from template..." -ForegroundColor Yellow
    
    # Create settings_production.py from settings.py
    $settings_content = Get-Content "myproject\settings.py" -Raw
    
    # Update settings for production
    $settings_content = $settings_content -replace "DEBUG = True", "DEBUG = False"
    $settings_content = $settings_content -replace "ALLOWED_HOSTS = \[\]", "ALLOWED_HOSTS = ['localhost', '127.0.0.1']"
    
    # Add security settings
    $security_settings = @"

# Security settings
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
"@
    
    $settings_content += $security_settings
    
    # Write to settings_production.py
    $settings_content | Out-File "myproject\settings_production.py" -Encoding utf8
    Write-Host "Created settings_production.py with production settings" -ForegroundColor Green
}

# Start the server using Waitress
Write-Host "Starting server with Waitress on port $PORT..." -ForegroundColor Green
Write-Host "Access the application at http://localhost:$PORT" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow

# Start the server
& $PYTHON_PATH -m waitress --listen=127.0.0.1:$PORT myproject.wsgi:application
