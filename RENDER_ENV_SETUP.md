# 🔧 Render Environment Variables Setup (Copy-Paste Guide)

## ⚠️ Current Error
```
password authentication failed for user beher
```

This means either:
1. The password is wrong
2. Environment variables are not set correctly
3. DATABASE_URL exists with wrong password

---

## ✅ SOLUTION: Set These 5 Variables in Render

### Step-by-Step Instructions

1. **Go to Render Dashboard**: https://dashboard.render.com
2. **Click your service** (probably "bestbeher")
3. **Click "Environment"** (left sidebar)
4. **Delete DATABASE_URL** if it exists (we'll use individual vars instead)

### Now Add These 5 Variables:

Click **"Add Environment Variable"** for each one:

---

#### 1️⃣ DATABASE_NAME
```
Key: DATABASE_NAME
Value: defaultdb
```

---

#### 2️⃣ DATABASE_USER  
```
Key: DATABASE_USER
Value: beher
```

---

#### 3️⃣ DATABASE_PASSWORD
```
Key: DATABASE_PASSWORD
Value: [YOUR PASSWORD FROM COCKROACHDB]
```

**How to get password:**
1. Go to CockroachDB Cloud
2. Click "Connect" on your cluster
3. Click "Regenerate password" 
4. Copy it immediately!
5. Paste it here (no spaces!)

---

#### 4️⃣ DATABASE_HOST
```
Key: DATABASE_HOST
Value: border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud
```

---

#### 5️⃣ DATABASE_PORT
```
Key: DATABASE_PORT
Value: 26257
```

---

## 🎯 Final Check

After adding all 5, you should see in Render Environment:

```
✅ DATABASE_NAME = defaultdb
✅ DATABASE_USER = beher
✅ DATABASE_PASSWORD = [your password]
✅ DATABASE_HOST = border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud
✅ DATABASE_PORT = 26257
```

**AND** ❌ NO `DATABASE_URL` variable!

---

## 🚀 Deploy

1. Click **"Save Changes"** (if visible)
2. Go to **"Events"** tab
3. Click **"Manual Deploy"** → **"Deploy latest commit"**
4. Watch the logs - migrations should run successfully!

---

## ❓ Common Mistakes

### Mistake 1: Password has spaces
- ❌ Wrong: ` mypassword ` (spaces)
- ✅ Right: `mypassword` (no spaces)

### Mistake 2: Wrong host
- ❌ Wrong: `border-peacock` (incomplete)
- ✅ Right: `border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud`

### Mistake 3: DATABASE_URL still exists
- If `DATABASE_URL` exists, it takes priority
- **Delete it** and use individual variables instead

### Mistake 4: Wrong port
- ❌ Wrong: `5432` (PostgreSQL port)
- ✅ Right: `26257` (CockroachDB port)

---

## 🔍 How to Verify It's Working

After deployment, check logs. You should see:

```
✅ Operations to perform:
✅   Apply all migrations: ...
✅ Running migrations:
✅   ...
```

**NOT:**
```
❌ password authentication failed
```

---

## 📞 Still Getting Errors?

1. **Regenerate password** in CockroachDB (get fresh copy)
2. **Check all 5 variables** are set exactly as shown
3. **Make sure DATABASE_URL is deleted**
4. **Redeploy** the service

---

## 🎉 Success!

Once migrations run successfully, your website is connected to CockroachDB! 🚀

