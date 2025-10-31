# 🗄️ CockroachDB Setup Guide for Render

## 📋 Database Connection Information

From your CockroachDB cluster:
- **Host**: `border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud`
- **Port**: `26257`
- **User**: `beher`
- **Database**: `defaultdb`
- **SSL Mode**: `verify-full` (required for CockroachDB)

## 🔧 Configuration Options

### **Option 1: Using DATABASE_URL (Recommended)**

Set the `DATABASE_URL` environment variable in Render with your complete connection string:

```
postgresql://beher:<YOUR-PASSWORD>@border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full
```

**Replace `<YOUR-PASSWORD>` with your actual SQL user password.**

### **Option 2: Using Individual Environment Variables**

Set these environment variables in Render Dashboard:

```
DATABASE_NAME=defaultdb
DATABASE_USER=beher
DATABASE_PASSWORD=<YOUR-PASSWORD>
DATABASE_HOST=border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud
DATABASE_PORT=26257
```

## 📝 Steps to Configure in Render

### Step 1: Get Your Password

1. If you forgot your password, click **"Regenerate password"** in the CockroachDB connection modal
2. Copy the new password (you won't be able to see it again!)

### Step 2: Set Environment Variables in Render

1. Go to your Render Dashboard → **Web Service** → **Environment**
2. Add or update these variables:

   **Option A - Single DATABASE_URL (Recommended):**
   ```
   DATABASE_URL=postgresql://beher:<YOUR-PASSWORD>@border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full
   ```

   **Option B - Individual Variables:**
   ```
   DATABASE_NAME=defaultdb
   DATABASE_USER=beher
   DATABASE_PASSWORD=<YOUR-PASSWORD>
   DATABASE_HOST=border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud
   DATABASE_PORT=26257
   ```

### Step 3: Remove Old Database References (if using CockroachDB instead of Render's database)

If you were using Render's PostgreSQL database, you can remove these from `render.yaml`:
- The `fromDatabase` reference for DATABASE_URL
- The `databases` section (unless you want to keep both)

Or update `render.yaml` to use environment variables directly.

## 🔒 SSL Certificate (Important for CockroachDB)

CockroachDB requires SSL verification. The settings are already configured to handle this:

- **For CockroachDB hosts**: Uses `sslmode=verify-full`
- **For other PostgreSQL hosts**: Uses `sslmode=require`

The SSL certificate is automatically handled by `psycopg2` and the connection string.

## ✅ Testing the Connection

After setting up the environment variables:

1. **Save** the environment variables in Render
2. **Redeploy** your service
3. Check the logs - migrations should run successfully
4. Your Django app will connect to CockroachDB

## 🚨 Important Notes

1. **Password Security**: Never commit passwords to git. Always use environment variables.

2. **SSL Required**: CockroachDB requires SSL. The settings automatically detect CockroachDB hosts and use `verify-full`.

3. **Compatibility**: CockroachDB is PostgreSQL-compatible, so Django will work seamlessly with it.

4. **Port**: CockroachDB uses port `26257` (not the standard PostgreSQL port `5432`).

## 🔍 Troubleshooting

### Connection Refused
- Verify the host and port are correct
- Check that your CockroachDB cluster is running
- Ensure firewall rules allow connections

### SSL Errors
- Make sure `sslmode=verify-full` is in your connection string
- Check that your `psycopg2-binary` version supports SSL

### Authentication Failed
- Verify the username (`beher`) and password are correct
- Check if you need to regenerate the password
- Ensure the user has permissions on the `defaultdb` database

## 📚 Additional Resources

- [CockroachDB Connection Strings](https://www.cockroachlabs.com/docs/stable/connection-strings.html)
- [Django Database Configuration](https://docs.djangoproject.com/en/stable/ref/settings/#databases)

