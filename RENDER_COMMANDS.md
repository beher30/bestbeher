# Render Deployment Commands - Correct Configuration

## 🎯 **For Render Dashboard Configuration**

Based on your project structure where **Root Directory** is set to `Website/myproject`:

### **Build Command** (No Database Access Needed)
```bash
cd ../.. && pip install -r requirements.txt && cd Website/myproject && python manage.py collectstatic --noinput
```

**Important**: Do NOT run migrations in the build command. The database may not be available during build.

### **Start Command** (Includes Migrations)
```bash
cd Website/myproject && python manage.py migrate --noinput && gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120
```

**Note**: Migrations run at the start of the service (when database is available) before Gunicorn starts.

---

## 🔄 **Alternative: If Root Directory is Empty**

If you **remove** the Root Directory setting (leave it empty), use:

### **Build Command**
```bash
pip install -r requirements.txt && cd Website/myproject && python manage.py collectstatic --noinput
```

### **Start Command** (Includes Migrations)
```bash
cd Website/myproject && python manage.py migrate --noinput && gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120
```

---

## ✅ **What Changed**

1. **Settings.py updated**: Now handles missing database credentials gracefully during build
2. **Build command**: Only installs dependencies and collects static files (no database needed)
3. **Migrations**: Moved to Pre-Deploy command or Start command (when database is available)

---

## 📝 **Steps to Fix Your Current Deployment**

1. Go to your Render Dashboard → Web Service → Settings
2. **Build Command**: Replace with:
   ```
   cd ../.. && pip install -r requirements.txt && cd Website/myproject && python manage.py collectstatic --noinput
   ```
3. **Start Command**: Replace with (includes migrations):
   ```
   cd Website/myproject && python manage.py migrate --noinput && gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120
   ```
5. Save and redeploy

---

## 🚨 **Important Notes**

- **$PORT**: Render automatically sets this - always use it in your start command
- **Database**: DATABASE_URL should be automatically linked if you connected the database service
- **Static Files**: Collected during build (no database needed)
- **Migrations**: Run during pre-deploy or start (when database is ready)

---

## 🔍 **Troubleshooting**

If you prefer to separate migrations, you can use Render's **Pre-Deploy Script** feature if available in your plan, or use a separate management command.

