# IntelliOptics 2.0 - Development Session Log
**Date:** January 26, 2026
**Session Focus:** Bug fixes, remote deployment, user authentication

---

## Summary

This session addressed multiple bugs in the cloud stack, improved remote deployment procedures, and added diagnostic tools for troubleshooting production deployments.

---

## Bug Fixes

### 1. Detector Description Not Saving on Create
**File:** `cloud/backend/app/routers/detectors.py`
**Issue:** When creating a new detector, the description field was not being saved.
**Fix:** Added `description=payload.description` to the Detector model instantiation.

```python
det = models.Detector(
    name=payload.name,
    description=payload.description,  # THIS LINE WAS ADDED
    query_text=payload.query_text,
    ...
)
```

### 2. MSAL/Azure AD Authentication Errors
**Files:**
- `cloud/frontend/src/utils/auth.ts`
- `cloud/frontend/src/App.tsx`
- `cloud/frontend/.env`

**Issue:** Console errors when Azure AD not configured (`endpoints_resolution_error`).
**Fix:** Added conditional MSAL initialization - only creates MSAL instance if properly configured.

```typescript
export const isMsalConfigured =
    clientId !== "YOUR_CLIENT_ID_HERE" &&
    clientId !== "placeholder-client-id" &&
    clientId !== "DISABLED" &&
    ...

export const msalInstance: PublicClientApplication | null = isMsalConfigured
    ? new PublicClientApplication(msalConfig)
    : null;
```

### 3. Form Validation Errors Not Displayed
**File:** `cloud/frontend/src/pages/DetectorConfigPage.tsx`
**Issue:** Save button appeared to do nothing when validation failed.
**Fix:** Added `onFormError` handler to show toast notifications for validation errors.

### 4. DetectorConfigPage Schema Null Handling
**File:** `cloud/frontend/src/pages/DetectorConfigPage.tsx`
**Issue:** `class_names: Invalid input` error when API returns null values.
**Fix:** Updated Zod schema to handle null values:

```typescript
class_names: z.array(z.string()).nullable().optional().transform(val => val ?? []),
```

### 5. Demo Stream Model Path Hardcoded
**File:** `cloud/backend/app/services/demo_session_manager.py`
**Issue:** Demo stream always looked for `{detector_id}/primary/model.onnx` instead of using detector's configured model path.
**Fix:** Now reads `primary_model_blob_path` from detector/config database records.

### 6. Demo Stream Confidence Not Parsing
**File:** `cloud/backend/app/services/demo_session_manager.py`
**Issue:** Confidence values showing as 0.0 - code looked for `conf` but worker returns `confidence`.
**Fix:** Updated to check both field names:

```python
confidence = best_detection.get("confidence", best_detection.get("conf", 0.0))
```

### 7. User Creation Missing Password
**Files:**
- `cloud/frontend/src/pages/AdminPage.tsx`
- `cloud/backend/app/routers/users.py`

**Issue:** Admin Panel user creation failed - frontend didn't send password, backend didn't hash/store it.
**Fix (Frontend):** Added password state and input field to create user form.
**Fix (Backend):** Import `get_password_hash` and store hashed password:

```python
from ..auth import get_password_hash

hashed_password = get_password_hash(payload.password)
user = models.User(email=payload.email, hashed_password=hashed_password, roles=payload.roles)
```

### 8. Browser Caching Stale JavaScript
**File:** `cloud/frontend/nginx.conf`
**Issue:** Old JS files cached in browser after deployment.
**Fix:** Added cache-control headers for index.html:

```nginx
location = /index.html {
    root /usr/share/nginx/html;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
    add_header Expires "0";
}
```

---

## New Features/Tools Added

### 1. Diagnostic Scripts
**Files:**
- `cloud/backend/app/diagnose_users.py` - Check DB connection and list users
- `cloud/backend/app/create_admin.py` - Create or reset admin user

**Usage:**
```powershell
docker exec -it intellioptics-cloud-backend python /app/app/diagnose_users.py
docker exec -it intellioptics-cloud-backend python /app/app/create_admin.py
```

### 2. Comprehensive Troubleshooting Guide
**File:** `install/README.md`
Added sections for:
- Database connection refused (Azure vs local PostgreSQL)
- Admin user creation
- User/detector save failures
- Browser cache issues
- Force update commands

---

## Documentation Updates

### 1. Path Spaces Warning
**Files:** `install/README.md`, `docs/QUICKSTART.md`
Added warning about avoiding spaces in installation paths.

### 2. Updated Path Examples
Changed all path examples from `C:\Dev\IntelliOptics 2.0` to `C:\intellioptics-2.0`

---

## Current Image Versions

| Image | Version | Changes |
|-------|---------|---------|
| backend | v2.0.3 | Model path fix, confidence parsing, user password hashing, diagnostic scripts |
| frontend | v2.0.2 | MSAL fix, form validation, password field in user creation, nginx cache headers |
| worker | v2.0.0 | No changes |

---

## Remote Deployment Learnings

### Database Configuration
The `install/.env` file must use the **local Docker PostgreSQL**, not Azure:

**Correct (local):**
```
POSTGRES_PASSWORD=YourSecurePassword123!
POSTGRES_DSN=postgresql://intellioptics:${POSTGRES_PASSWORD}@postgres:5432/intellioptics
```

**Incorrect (Azure - won't work without network access):**
```
POSTGRES_DSN=postgresql://...@pg-intellioptics.postgres.database.azure.com:5432/...
```

### Update Procedure for Remote Machines
```powershell
cd "C:\intellioptics-2.0\install"
git pull
az acr login --name acrintellioptics
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --force-recreate
```

### Admin User Setup on Fresh Install
```powershell
docker exec -it intellioptics-cloud-backend python /app/app/create_admin.py
```

Default credentials (defined in `seed_admin.py`):
- Email: `jmorgan@4wardmotions.com`
- Password: `g@za8560EYAS`

---

## Files Modified This Session

### Backend
- `cloud/backend/app/routers/detectors.py` - Description field fix
- `cloud/backend/app/routers/users.py` - Password hashing fix
- `cloud/backend/app/services/demo_session_manager.py` - Model path and confidence fixes
- `cloud/backend/app/diagnose_users.py` - NEW
- `cloud/backend/app/create_admin.py` - NEW

### Frontend
- `cloud/frontend/src/utils/auth.ts` - MSAL conditional init
- `cloud/frontend/src/App.tsx` - MSAL guard
- `cloud/frontend/src/pages/DetectorConfigPage.tsx` - Schema and error handling
- `cloud/frontend/src/pages/AdminPage.tsx` - Password field
- `cloud/frontend/nginx.conf` - Cache headers
- `cloud/frontend/.env` - DISABLED values

### Documentation
- `install/README.md` - Troubleshooting guide
- `docs/QUICKSTART.md` - Path updates
- `install/docker-compose.prod.yml` - Version bumps

---

## Git Commits This Session

1. `7cad3e5` - Fix detector description not saving on create
2. `96bfc9e` - Bump backend image to v2.0.1
3. `8bffcdf` - Fix frontend authentication and form validation issues
4. `1df67b9` - docs: update paths to avoid spaces, add .env troubleshooting
5. `e598c04` - Fix demo stream inference: use correct model path and confidence field
6. `a2285e7` - Bump backend image to v2.0.2
7. `b36748a` - Bump frontend image to v2.0.1
8. `33ce66c` - Fix user creation in Admin Panel - add password field
9. `1d50e0f` - Fix user creation to hash and store password
10. `624d98b` - Add diagnostic and admin creation scripts
11. `6adda0b` - Fix import paths in diagnostic scripts
12. `10a167e` - Add comprehensive troubleshooting guide to install README

---

## Known Issues / Future Work

1. **intellioptics-api-37558 hardcoded** - Edge inference code has hardcoded Azure API URL in `edge/edge-api/app/core/edge_inference.py:379`. Should be parameterized.

2. **YOLOWorld model dependency** - Edge stack requires YOLOWorld model file (`yolov8s-worldv2.pt`) which must be downloaded separately or use pre-built ACR images.

3. **Low memory edge devices** - Devices with 8GB RAM may have slower YOLOWorld inference times.

---

## Architecture Notes

### Cloud Failover / Alerting
- **Cloud failover**: Nginx on edge has `@cloud_fallback` for 404/422/503 errors
- **Escalation**: Low confidence predictions escalated via SDK to cloud
- **Alerting**: Handled by cloud backend directly via SendGrid/Twilio (no Azure API dependency)

### Model Storage
- Models stored in Azure Blob Storage: `intelliopticsweb37558.blob.core.windows.net/models/`
- Path format: `{detector_id}/primary/intellioptics-yolov10n.onnx`
- Downloaded locally to edge devices after initial config

---

## Environment

- **Dev Machine:** Windows, C:\dev\IntelliOptics 2.0
- **Remote Test Machine:** Windows, C:\intellioptics-2.0
- **Docker Desktop:** Running cloud stack
- **Azure ACR:** acrintellioptics.azurecr.io

---

## Next Steps for Future Sessions

1. Test full edge stack deployment
2. Verify YOLOWorld inference on edge devices
3. Parameterize hardcoded Azure API URL in edge code
4. Consider adding automated admin seeding on first startup
5. Add health check endpoint that verifies DB connectivity
