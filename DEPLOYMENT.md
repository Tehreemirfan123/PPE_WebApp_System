# PPE Web App Deployment Guide

This guide uses services that can be used without adding card details:

- Database: Supabase Free PostgreSQL
- Backend API: Hugging Face Spaces with Docker
- Dashboard: Streamlit Community Cloud
- ML pipeline: runs locally on your laptop/PC and sends events to the cloud API

Important free-tier notes:

- Hugging Face Spaces free CPU apps can sleep or restart after inactivity.
- Supabase Free has storage limits. This project stores new violation frames as compressed base64 strings in the database for FYP/demo use.
- The YOLO/OpenVINO ML pipeline should stay local. Do not deploy the ML pipeline to Hugging Face or Streamlit Cloud.
- This is suitable for a final-year-project demo, not a paid production safety system.

## Phase 0: Push Your Latest Code To GitHub

Open PowerShell.

Go to your project folder:

```powershell
cd "c:\Users\Tehreem Irfan\Documents\Final Year Project\PPE_WebApp_System"
```

Check changed files:

```powershell
git status
```

Add all deployment changes:

```powershell
git add .
```

Commit:

```powershell
git commit -m "Prepare Hugging Face backend deployment"
```

Push to GitHub:

```powershell
git push origin main
```

Open this in your browser:

```text
https://github.com/Tehreemirfan123/PPE_WebApp_System
```

Confirm these files exist:

- `Dockerfile`
- `.dockerignore`
- `requirements-backend.txt`
- `frontend/requirements.txt`
- `backend/main.py`
- `database/001_init_schema.sql`
- `database/002_seed_defaults.sql`

## Phase 1: Supabase Database

You already completed this if both SQL files showed:

```text
Success. No rows returned
```

The database setup order is:

1. Run `database/001_init_schema.sql`
2. Run `database/002_seed_defaults.sql`

Default logins after seeding:

```text
Admin: admin@ppe.com / admin123
Officer: officer@ppe.com / officer123
```

Now copy your Supabase PostgreSQL connection URL:

1. Open Supabase.
2. Open your project.
3. Click the gear icon for `Project Settings`.
4. Click `Database`.
5. Find `Connection string`.
6. Choose the URI / pooler connection string.
7. Copy it.
8. Replace `[YOUR-PASSWORD]` with your real database password.

It should look similar to:

```text
postgresql://postgres.xxxxx:YOUR_REAL_PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres
```

If your copied URL does not already end with query settings, add SSL mode at the end:

```text
?sslmode=require
```

Final example:

```text
postgresql://postgres.xxxxx:YOUR_REAL_PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require
```

Save this URL. You will use it as `DATABASE_URL`.

## Phase 2: Deploy Backend API On Hugging Face Spaces

Open your browser and go to:

```text
https://huggingface.co
```

Create an account or sign in.

### Create The Backend Space

Click your profile picture in the top-right.

Click `New Space`.

Use these settings:

```text
Space name: ppe-backend-api
License: MIT
SDK: Docker
Hardware: CPU basic / Free
Visibility: Public
```

Click `Create Space`.

Your backend URL will be:

```text
https://YOUR_HF_USERNAME-ppe-backend-api.hf.space
```

Replace `YOUR_HF_USERNAME` with your actual Hugging Face username.

Example:

```text
https://tehreemirfan-ppe-backend-api.hf.space
```

### Add Backend Secrets

Inside your Hugging Face Space, click `Settings`.

Find `Variables and secrets`.

Add these as **secrets**:

```text
DATABASE_URL
```

Value:

```text
paste your full Supabase PostgreSQL URI
```

Add:

```text
SECRET_KEY
```

Generate it in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the generated output as the value.

Add:

```text
BACKEND_URL
```

Value:

```text
https://YOUR_HF_USERNAME-ppe-backend-api.hf.space
```

Add:

```text
SAVED_VIOLATIONS_DIR
```

Value:

```text
/tmp/saved_violations
```

Add:

```text
PORT
```

Value:

```text
7860
```

### Push Your Code To The Hugging Face Space

Hugging Face Spaces are Git repositories. You will push this project to the Space.

In Hugging Face, open:

```text
https://huggingface.co/settings/tokens
```

Click `New token`.

Use:

```text
Token name: ppe-space-deploy
Role: Write
```

Create the token and copy it. Keep it private.

In PowerShell, from your project folder:

```powershell
cd "c:\Users\Tehreem Irfan\Documents\Final Year Project\PPE_WebApp_System"
```

Add the Hugging Face Space as a Git remote. Replace `YOUR_HF_USERNAME`:

```powershell
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/ppe-backend-api
```

If PowerShell says `remote hf already exists`, run this instead:

```powershell
git remote set-url hf https://huggingface.co/spaces/YOUR_HF_USERNAME/ppe-backend-api
```

Push your `main` branch to Hugging Face:

```powershell
git push hf main:main
```

If PowerShell asks for login:

```text
Username: your Hugging Face username
Password: paste your Hugging Face write token
```

If the push is rejected because the new Space already created a README, and this is a brand-new empty Space, run:

```powershell
git push hf main:main --force
```

Only use that force command for this new Hugging Face Space. It does not force-push your GitHub repository.

### Wait For Build

Go back to your Hugging Face Space in the browser.

Click `Logs`.

Wait until the Docker build finishes.

When it is running, open:

```text
https://YOUR_HF_USERNAME-ppe-backend-api.hf.space/health
```

Expected response:

```json
{"status":"healthy"}
```

Also open:

```text
https://YOUR_HF_USERNAME-ppe-backend-api.hf.space/
```

Expected response:

```json
{"status":"ok","message":"PPE Detection System API is running"}
```

## Phase 3: Deploy Streamlit Dashboard

Open your browser and go to:

```text
https://share.streamlit.io
```

Sign in with GitHub.

Click `Create app`.

Choose `Yup, I have an app`.

Fill in:

```text
Repository: Tehreemirfan123/PPE_WebApp_System
Branch: main
Main file path: frontend/app.py
```

Click `Advanced settings`.

In `Secrets`, paste this. Replace `YOUR_HF_USERNAME`:

```toml
BACKEND_API_URL = "https://YOUR_HF_USERNAME-ppe-backend-api.hf.space"
```

Click `Deploy`.

Wait until Streamlit finishes installing dependencies.

Open the Streamlit app URL.

Test login:

```text
admin@ppe.com
admin123
```

Then test:

```text
officer@ppe.com
officer123
```

## Phase 4: Point Local ML Pipeline To The Cloud Backend

This part stays on your computer.

Open:

```text
ml_pipeline/config.yaml
```

Find:

```yaml
api_base_url:   http://127.0.0.1:8000
api_email:      admin@ppe.com
api_password:   admin123
```

Change it to your Hugging Face backend URL:

```yaml
api_base_url:   https://YOUR_HF_USERNAME-ppe-backend-api.hf.space
api_email:      admin@ppe.com
api_password:   admin123
```

Keep this for first test:

```yaml
video_source:   "ml_pipeline/test_videos/demo.mp4"
```

Run the pipeline locally:

```powershell
cd "c:\Users\Tehreem Irfan\Documents\Final Year Project\PPE_WebApp_System"
.\venv\Scripts\activate
python ml_pipeline/main.py
```

Refresh Streamlit and open `Violation Logs`.

New violations should appear in the cloud dashboard.

## Phase 5: Final Demo Checklist

Check these in order:

1. Supabase project is active.
2. Hugging Face backend opens at `/health`.
3. Streamlit dashboard opens.
4. Admin login works.
5. Officer login works.
6. Dashboard pages load without backend connection errors.
7. Local ML pipeline authenticates successfully.
8. New violation appears in `Violation Logs`.
9. New violation frame image appears.
10. Officer account can mark a violation as resolved.

## Useful Commands

Check changed files:

```powershell
git status
```

Push updates to GitHub:

```powershell
git add .
git commit -m "Update deployment files"
git push origin main
```

Push updates to Hugging Face backend Space:

```powershell
git push hf main:main
```

Run backend locally:

```powershell
.\venv\Scripts\activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Run dashboard locally in another PowerShell window:

```powershell
.\venv\Scripts\activate
$env:BACKEND_API_URL="http://127.0.0.1:8000"
streamlit run frontend/app.py
```

Run ML pipeline locally:

```powershell
.\venv\Scripts\activate
python ml_pipeline/main.py
```

## Troubleshooting

If Hugging Face build fails:

- Open Space `Logs`.
- Confirm Space SDK is `Docker`.
- Confirm `Dockerfile` exists at the repository root.
- Confirm `requirements-backend.txt` exists.

If backend says database connection failed:

- Check the `DATABASE_URL` secret in Hugging Face Space settings.
- Make sure your Supabase password is inside the URL.
- Make sure there are no square brackets around the password.

If `/health` does not open:

- Wait a few minutes and check Space logs.
- Confirm `PORT` is set to `7860`.
- Confirm the Space is running on free CPU hardware.

If Streamlit cannot connect to backend:

- Open Streamlit app settings.
- Check the secret name is exactly `BACKEND_API_URL`.
- Make sure it starts with `https://`.
- Open the Hugging Face `/health` URL once to wake the backend.

If violation images do not show:

- Make sure `ml_pipeline/backend_client.py` is updated.
- Run the local pipeline again.
- Old records may only contain local filenames; new records should contain base64 image data.

If Supabase SQL fails:

- Run `001_init_schema.sql` first.
- Run `002_seed_defaults.sql` second.
- Do not run both files at the same time.
