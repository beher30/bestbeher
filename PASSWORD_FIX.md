# 🔐 CockroachDB Password Authentication Fix

## ❌ Current Error
```
password authentication failed for user beher
```

## ✅ Solution: Use Individual Environment Variables (Recommended)

Instead of using `DATABASE_URL` with a potentially incorrectly encoded password, use individual environment variables. This avoids URL encoding issues.

### Step 1: Get Your Password

1. Go to your CockroachDB cluster dashboard
2. Click **"Connect"** on your cluster
3. Click **"Regenerate password"** if you don't have it
4. **Copy the password immediately** (you won't see it again!)

### Step 2: Set Environment Variables in Render

Go to **Render Dashboard → Your Web Service → Environment** and add these variables:

```
DATABASE_NAME=defaultdb
DATABASE_USER=beher
DATABASE_PASSWORD=<paste-your-password-here>
DATABASE_HOST=border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud
DATABASE_PORT=26257
```

**Important**: 
- Replace `<paste-your-password-here>` with the actual password from Step 1
- Make sure there are no extra spaces before/after the password
- Copy the password exactly as shown

### Step 3: Remove DATABASE_URL (if set)

If you previously set `DATABASE_URL`, **delete it** from the Environment Variables in Render. The individual variables will be used instead.

### Step 4: Save and Redeploy

1. Click **"Save Changes"** in Render
2. The service will automatically redeploy
3. Check the logs - migrations should now succeed

---

## 🔄 Alternative: Fix DATABASE_URL (If you prefer)

If you want to use `DATABASE_URL`, you need to URL-encode special characters in the password.

### Common Characters That Need Encoding:
- `@` → `%40`
- `#` → `%23`
- `$` → `%24`
- `%` → `%25`
- `&` → `%26`
- `+` → `%2B`
- `=` → `%3D`
- `?` → `%3F`
- `/` → `%2F`
- `:` → `%3A`
- ` ` (space) → `%20` or `+`

### Example:
If your password is `P@ssw0rd#123`, the DATABASE_URL should be:
```
postgresql://beher:P%40ssw0rd%23123@border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full
```

### URL Encoding Tool:
You can use Python to encode your password:
```python
from urllib.parse import quote
password = "your-password-here"
encoded = quote(password, safe='')
print(encoded)
```

---

## 🧪 Testing Your Connection

After setting the environment variables, you can test the connection by checking the Render logs. Look for:
- ✅ `Operations to perform: Apply all migrations`
- ✅ `Running migrations:`
- ❌ `password authentication failed` (should not appear)

---

## 🔍 Troubleshooting

### Still Getting Password Errors?

1. **Double-check the password**: Copy it again from CockroachDB
2. **Check for hidden characters**: Try regenerating the password
3. **Verify the username**: Should be `beher` (case-sensitive)
4. **Check database name**: Should be `defaultdb`
5. **Ensure SSL is enabled**: The settings automatically handle this

### Password Has Special Characters?

**Use individual environment variables** instead of DATABASE_URL - this avoids all URL encoding issues!

---

## ✅ Quick Checklist

- [ ] Copied password from CockroachDB (or regenerated it)
- [ ] Set `DATABASE_PASSWORD` in Render environment variables
- [ ] Set `DATABASE_USER=beher`
- [ ] Set `DATABASE_HOST=border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud`
- [ ] Set `DATABASE_PORT=26257`
- [ ] Set `DATABASE_NAME=defaultdb`
- [ ] Removed `DATABASE_URL` (if using individual variables)
- [ ] Saved and redeployed

