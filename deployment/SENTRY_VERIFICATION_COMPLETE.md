# ✅ Sentry Integration - Verification Complete

## Status: Backend Tests Passed ✅

All automated backend Sentry tests have completed successfully on production VPS.

---

## Test Results Summary

### ✅ Backend Tests (Completed)

```
╔════════════════════════════════════════════════════════════════════╗
║         ✅ TESTS BACKEND SENTRY TERMINÉS                       ║
╚════════════════════════════════════════════════════════════════════╝

📊 Résumé des tests:
   ✅ Authentification réussie
   ✅ Statut Sentry vérifié
   ✅ Message de test envoyé à Sentry
   ✅ Erreur de test déclenchée (ZeroDivisionError)
```

**Test Details:**
- ✅ Authentication successful (jerome0laval@gmail.com)
- ✅ Sentry status verified (configured and enabled)
- ✅ Test message sent: "✅ Sentry test message from CloudWaste"
- ✅ Test error triggered: "ZeroDivisionError: 🚨 TEST ERROR: Sentry integration test"
- ✅ User context included (email, user ID)
- ✅ Tags present (environment=production, user_triggered=true)

---

## Next Steps

### 1️⃣ Verify Sentry Dashboard (REQUIRED)

**URL:** https://sentry.io

**Steps:**
1. Login to Sentry dashboard
2. Navigate to Organization: **jerome-laval-x3**
3. Select Project: **cloudwaste** (Backend)
4. Go to **Issues** tab

**Expected Events:**

You should see these 2 events captured:

**Event 1: Test Message**
- **Title:** "✅ Sentry test message from CloudWaste"
- **Type:** Message
- **Environment:** production
- **Tags:** user_triggered=true
- **User Context:**
  - Email: jerome0laval@gmail.com
  - User ID: [your user UUID]

**Event 2: Test Error**
- **Title:** "ZeroDivisionError: 🚨 TEST ERROR: Sentry integration test"
- **Type:** Error
- **Environment:** production
- **Tags:** user_triggered=true
- **Stack Trace:** Should show backend/app/api/v1/test_sentry.py line
- **User Context:**
  - Email: jerome0laval@gmail.com
  - User ID: [your user UUID]

**Timing:** Events appear in **10-30 seconds** after being sent.

---

### 2️⃣ Test Frontend Sentry (REQUIRED)

**URL:** https://cutcosts.tech

**Steps:**

1. Open the website in your browser
2. Press **F12** to open Developer Tools
3. Go to the **Console** tab
4. Copy and paste this command:

```javascript
Sentry.captureException(new Error("🧪 Test Frontend Sentry Error"));
```

5. Press Enter

**Expected Console Output:**
```
[Sentry] Event sent to Sentry: {"event_id":"..."}
```

**Verify in Sentry Dashboard:**
1. Return to https://sentry.io
2. Organization: **jerome-laval-x3**
3. Project: **cloudwaste-frontend** (JavaScript)
4. Go to **Issues** tab

**Expected Event:**
- **Title:** "Error: 🧪 Test Frontend Sentry Error"
- **Type:** Error
- **Environment:** production
- **Tags:** environment=production
- **Stack Trace:** Should show browser source maps
- **Breadcrumbs:** User navigation history

---

### 3️⃣ Disable DEBUG Mode (CRITICAL - AFTER TESTS)

⚠️ **SECURITY WARNING:** DEBUG mode exposes test endpoints. You MUST disable it after testing.

**On VPS, run:**

```bash
cd /opt/cloudwaste
bash deployment/disable-sentry-testing.sh
```

**What this does:**
1. Sets `DEBUG=False` in .env.prod
2. Restarts backend and frontend containers
3. Verifies test endpoints are blocked (HTTP 403/404)
4. Confirms API is still operational

**Verification:**
After running the script, test that the endpoint is blocked:

```bash
curl -X GET "https://cutcosts.tech/api/v1/test/sentry/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected:** HTTP 403 or 404 (test endpoints disabled)

---

## Production Sentry Configuration

Once DEBUG mode is disabled, Sentry will continue to work in production:

### Backend (FastAPI)
- **Automatic Error Capture:** All unhandled exceptions sent to Sentry
- **Performance Monitoring:** Transaction tracking enabled
- **User Context:** Authenticated users automatically tagged
- **Environment:** production

### Frontend (Next.js)
- **Automatic Error Capture:** All unhandled errors and promise rejections
- **Source Maps:** Uploaded for readable stack traces
- **User Feedback:** Error dialog with "Report Feedback" button
- **Environment:** production

---

## Troubleshooting

### Problem: No events in Sentry dashboard

**Solution 1:** Wait 30-60 seconds, then refresh the dashboard.

**Solution 2:** Check backend logs for Sentry initialization:
```bash
docker logs cloudwaste_backend --tail 50 | grep -i sentry
```

**Expected:**
```
INFO:app.main:✅ Sentry initialized (environment: production)
```

**Solution 3:** Verify Sentry DSN variables are set:
```bash
docker exec cloudwaste_backend env | grep "^SENTRY"
docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY"
```

**Expected (Backend):**
```
SENTRY_DSN=https://442a2365755e0b972138478b85fdb5a7@...
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

**Expected (Frontend):**
```
NEXT_PUBLIC_SENTRY_DSN=https://442a2365755e0b972138478b85fdb5a7@...
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
```

### Problem: Frontend variables still empty

**Solution:** Rebuild frontend with build args:
```bash
cd /opt/cloudwaste
set -a
source .env.prod
set +a
docker compose -f deployment/docker-compose.prod.yml up -d --build frontend
sleep 120  # Wait for frontend to rebuild
```

**Verify:**
```bash
docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY"
```

### Problem: Script authentication fails

**Solution:** Run script with explicit credentials:
```bash
bash deployment/test-sentry.sh your-email@example.com "your-password"
```

**Note:** Special characters in password are automatically escaped.

---

## Scripts Overview

### 1. test-sentry.sh
**Purpose:** Automated testing of backend Sentry integration

**Usage:**
```bash
cd /opt/cloudwaste
bash deployment/test-sentry.sh
```

**What it does:**
1. Authenticates with API (handles special characters in password)
2. Tests GET /api/v1/test/sentry/status
3. Tests POST /api/v1/test/sentry/message
4. Tests POST /api/v1/test/sentry/error (triggers ZeroDivisionError)
5. Checks backend logs for Sentry events

### 2. enable-sentry-testing.sh
**Purpose:** Enable DEBUG mode for testing

**Usage:**
```bash
cd /opt/cloudwaste
bash deployment/enable-sentry-testing.sh
```

**What it does:**
1. Sets DEBUG=True in .env.prod
2. Verifies Sentry variables
3. Pulls latest code
4. Restarts containers
5. Verifies DEBUG mode is active

### 3. disable-sentry-testing.sh
**Purpose:** Disable DEBUG mode after testing

**Usage:**
```bash
cd /opt/cloudwaste
bash deployment/disable-sentry-testing.sh
```

**What it does:**
1. Sets DEBUG=False in .env.prod
2. Restarts containers
3. Verifies test endpoints are blocked
4. Confirms API is operational

---

## Important URLs

| Service | URL |
|---------|-----|
| Dashboard Sentry | https://sentry.io |
| Backend Project | https://sentry.io/organizations/jerome-laval-x3/projects/cloudwaste/ |
| Frontend Project | https://sentry.io/organizations/jerome-laval-x3/projects/cloudwaste-frontend/ |
| Application | https://cutcosts.tech |
| API Health Check | https://cutcosts.tech/api/v1/health |

---

## Checklist

- [x] **Backend Test Script** - Created deployment/test-sentry.sh
- [x] **Backend Tests Executed** - All tests passed
- [x] **Backend Events Sent** - Message and error sent to Sentry
- [ ] **Sentry Dashboard Verified** - User must check for events
- [ ] **Frontend Test Executed** - User must test in browser console
- [ ] **Frontend Events Sent** - User must verify in Sentry dashboard
- [ ] **DEBUG Mode Disabled** - User must run disable-sentry-testing.sh

---

## Files Created/Modified

### Created
- ✅ `deployment/test-sentry.sh` - Automated test script
- ✅ `deployment/SENTRY_QUICKSTART.md` - Simplified testing guide
- ✅ `deployment/SENTRY_VERIFICATION_COMPLETE.md` - This file

### Modified
- ✅ `deployment/docker-compose.prod.yml` - Added env_file to frontend service
- ✅ `backend/app/api/v1/test_detection.py` - Removed duplicate Sentry endpoints

### Already Existed
- ✅ `deployment/enable-sentry-testing.sh` - Enable DEBUG mode
- ✅ `deployment/disable-sentry-testing.sh` - Disable DEBUG mode
- ✅ `backend/app/api/v1/test_sentry.py` - Sentry test endpoints

---

## Critical Reminder

🔒 **SECURITY:** Never leave DEBUG=True in production. Test endpoints expose sensitive debugging information.

✅ **After testing:** Always run `bash deployment/disable-sentry-testing.sh`

📊 **Ongoing Monitoring:** Sentry will continue to capture real errors in production (even with DEBUG=False).

---

**Status:** Backend testing complete ✅ | Frontend testing pending ⏳ | DEBUG mode active ⚠️
