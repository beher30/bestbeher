# 🚨 QUICK FIX: Password Authentication Error

## The Problem
```
password authentication failed for user beher
```

## ✅ Solution (5 Minutes)

### Step 1: Get Your CockroachDB Password

1. Go to your **CockroachDB Cloud Dashboard**
2. Click on your cluster: **border-peacock**
3. Click **"Connect"** button
4. Click **"Regenerate password"** if you don't have it
5. **IMPORTANT**: Copy the password RIGHT NOW (you won't see it again!)

### Step 2: Set Environment Variables in Render

1. Go to **Render Dashboard** → https://dashboard.render.com
2. Click on your web service (probably named **bestbeher** or **beherbest**)
3. Click **"Environment"** tab (left sidebar)
4. Click **"Add Environment Variable"** button

Add these **5 variables** one by one:

#### Variable 1:
- **Key**: `DATABASE_NAME`
- **Value**: `defaultdb`
- Click **Save**

#### Variable 2:
- **Key**: `DATABASE_USER`
- **Value**: `beher`
- Click **Save**

#### Variable 3:
- **Key**: `DATABASE_PASSWORD`
- **Value**: `<paste the password you copied from CockroachDB>`
- ⚠️ Make sure there are NO spaces before or after the password
- Click **Save**

#### Variable 4:
- **Key**: `DATABASE_HOST`
- **Value**: `border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud`
- Click **Save**

#### Variable 5:
- **Key**: `DATABASE_PORT`
- **Value**: `26257`
- Click **Save**

### Step 3: Remove DATABASE_URL (If It Exists)

1. Scroll through your environment variables
2. If you see `DATABASE_URL`, **DELETE it** (click the trash icon)
3. We're using individual variables instead

### Step 4: Verify Your Variables

Make sure you have exactly these 5 variables set:
- ✅ DATABASE_NAME
- ✅ DATABASE_USER  
- ✅ DATABASE_PASSWORD
- ✅ DATABASE_HOST
- ✅ DATABASE_PORT

### Step 5: Save and Redeploy

1. Scroll to the top of the Environment page
2. Click **"Save Changes"** (if visible)
3. Go to **"Events"** or **"Logs"** tab
4. Click **"Manual Deploy"** → **"Deploy latest commit"**
5. Wait for deployment to complete
6. Check logs - you should see migrations running successfully

---

## 🔍 Verify It Worked

After deployment, check the logs. You should see:
```
Operations to perform:
  Apply all migrations: ...
Running migrations:
  ...
```

**NOT** this error:
```
password authentication failed
```

---

## ❌ Still Not Working?

### Check 1: Password Correct?
- Go back to CockroachDB and regenerate password
- Make sure you copied it correctly (no extra spaces)

### Check 2: Variables Set?
- Go to Render → Environment
- Make sure all 5 variables are there
- Make sure values are correct (especially DATABASE_HOST)

### Check 3: Case Sensitive?
- Username: `beher` (lowercase)
- Database: `defaultdb` (lowercase)
- Host: exact match with the connection string

### Check 4: No Extra Spaces?
- When pasting password, make sure no leading/trailing spaces

---

## 📞 Still Stuck?

1. Take a screenshot of your Render Environment variables (hide the password!)
2. Verify your CockroachDB cluster is running
3. Double-check the host name matches exactly

---

## ✅ Success Checklist

- [ ] Got password from CockroachDB
- [ ] Set DATABASE_NAME=defaultdb
- [ ] Set DATABASE_USER=beher  
- [ ] Set DATABASE_PASSWORD=<your-password>
- [ ] Set DATABASE_HOST=border-peacock-9993.jxf.gcp-europe-west1.cockroachlabs.cloud
- [ ] Set DATABASE_PORT=26257
- [ ] Removed DATABASE_URL (if it existed)
- [ ] Saved and redeployed
- [ ] Migrations ran successfully in logs

