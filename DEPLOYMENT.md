# PPE Web App Deployment Guide

This guide deploys this exact project with free tiers and no card details:

- Database: Supabase Free PostgreSQL
- Backend API: Render Free Web Service
- Dashboard: Streamlit Community Cloud
- ML pipeline: runs locally on your laptop/PC and sends events to the cloud API

Important free-tier notes:

- Render Free web services sleep after inactivity and can take about a minute to wake up.
- Render Free does not provide persistent disks. This project stores violation frame previews inside the database as compressed base64 strings for demo/FYP use.
- Supabase Free has a 500 MB database limit and can pause after inactivity. If you generate many violations, delete old rows from `violations` and `detection_events`.
- Do not deploy this as a real production safety system on free tiers.

## Phase 0: Check And Push Your Code To GitHub

Open PowerShell.

Go to your project folder:

```powershell
cd "c:\Users\Tehreem Irfan\Documents\Final Year Project\PPE_WebApp_System"
```

Check your Git branch and changed files:

```powershell
git branch --show-current
git status
```

You should be on `main`. Add all deployment files:

```powershell
git add .
```

Commit them:

```powershell
git commit -m "Prepare PPE web app for free cloud deployment"
```

Push to GitHub:

```powershell
git push origin main
```

Open your browser and go to:

```text
https://github.com/Tehreemirfan123/PPE_WebApp_System
```

Confirm these files are visible in GitHub:

- `backend.Dockerfile`
- `requirements-backend.txt`
- `frontend/requirements.txt`
- `database/001_init_schema.sql`
- `database/002_seed_defaults.sql`
- `frontend/app.py`
- `ml_pipeline/config.yaml`

## Phase 1: Create Supabase Database

Open your browser and go to:

```text
https://supabase.com
```

Sign in with GitHub.

Click `New project`.

Use these values:

- Project name: `ppe-database`
- Database password: click generate, then copy and save it
- Region: choose the closest free region to you
- Plan: Free

Click `Create new project`.

Wait until the project finishes provisioning.

### Run The Schema

In Supabase, open the left sidebar and click `SQL Editor`.

Click `New query`.

On your computer, open:

```text
database/001_init_schema.sql
```

Copy the full file contents.

Paste it into the Supabase SQL editor.

Click `Run`.

You should see a success message.

### Run The Seed Data

In the same Supabase SQL editor, delete the old query text.

On your computer, open:

```text
database/002_seed_defaults.sql
```

Copy the full file contents.

Paste it into Supabase.

Click `Run`.

This creates the default logins:

- Admin: `admin@ppe.com` / `admin123`
- Officer: `officer@ppe.com` / `officer123`

### Copy The Database URL

In Supabase, click the gear icon for `Project Settings`.

Click `Database`.

Find `Connection string`.

Choose the URI / pooler connection string. It will look similar to:

```text
postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres
```

Replace `[YOUR-PASSWORD]` with the password you saved.

Save the final URL somewhere safe. You will paste it into Render.

## Phase 2: Deploy The Backend API On Render

Open your browser and go to:

```text
https://render.com
```

Sign in with GitHub.

Click `New +`.

Click `Web Service`.

Choose `Build and deploy from a Git repository`.

Connect this repository:

```text
Tehreemirfan123/PPE_WebApp_System
```

If Render asks for GitHub permission, click `Configure GitHub App`, allow access to this repository, then return to Render.

Use these service settings:

- Name: `ppe-backend-api`
- Language / Runtime: Docker
- Branch: `main`
- Dockerfile path: `backend.Dockerfile`
- Instance type: Free

Do not add a disk. Disks are not available on Render Free.

Open the advanced/environment variables section.

Add these environment variables:

```text
DATABASE_URL=<paste your Supabase PostgreSQL URI here>
SECRET_KEY=<paste a long random secret here>
BACKEND_URL=https://ppe-backend-api.onrender.com
SAVED_VIOLATIONS_DIR=/tmp/saved_violations
PORT=8000
```

To generate a secure `SECRET_KEY`, run this in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and use it as `SECRET_KEY`.

Click `Create Web Service`.

Wait for Render to build and deploy. It can take several minutes.

When the service is live, open this URL in your browser:

```text
https://ppe-backend-api.onrender.com/health
```

Expected response:

```json
{"status":"healthy"}
```

Also test the root URL:

```text
https://ppe-backend-api.onrender.com/
```

Expected response:

```json
{"status":"ok","message":"PPE Detection System API is running"}
```

If your Render URL is different, copy the actual URL and use that exact URL in the next phases.

## Phase 3: Deploy The Streamlit Dashboard

Open your browser and go to:

```text
https://share.streamlit.io
```

Sign in with GitHub.

Click `Create app`.

Choose `Yup, I have an app`.

Fill in:

- Repository: `Tehreemirfan123/PPE_WebApp_System`
- Branch: `main`
- Main file path: `frontend/app.py`

Open `Advanced settings`.

In `Secrets`, paste this:

```toml
BACKEND_API_URL = "https://ppe-backend-api.onrender.com"
```

If Render gave you a different backend URL, use that instead.

Click `Deploy`.

Wait until Streamlit finishes installing dependencies and starts the app.

Open the Streamlit app URL.

Log in with:

```text
admin@ppe.com
admin123
```

Then also test:

```text
officer@ppe.com
officer123
```

## Phase 4: Point The Local ML Pipeline To The Cloud Backend

This part stays on your own computer. Do not deploy the YOLO/OpenVINO pipeline to Render or Streamlit.

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

Change it to:

```yaml
api_base_url:   https://ppe-backend-api.onrender.com
api_email:      admin@ppe.com
api_password:   admin123
```

Use your actual Render URL if it is different.

Keep the demo video for first test:

```yaml
video_source:   "ml_pipeline/test_videos/demo.mp4"
```

Open PowerShell in the project root:

```powershell
cd "c:\Users\Tehreem Irfan\Documents\Final Year Project\PPE_WebApp_System"
```

Activate your local virtual environment:

```powershell
.\venv\Scripts\activate
```

Run the pipeline:

```powershell
python ml_pipeline/main.py
```

The pipeline should log in to the cloud backend and send violations to Supabase through Render.

Refresh the Streamlit dashboard and open `Violation Logs`.

## Phase 5: Final Demo Checklist

Before your FYP demo, check these in order:

1. Supabase project is not paused.
2. Render backend opens at `/health`.
3. Streamlit dashboard opens and can log in.
4. `Violation Logs` loads without backend connection errors.
5. Local ML pipeline starts without authentication errors.
6. A new violation appears in the dashboard after the pipeline runs.
7. Violation frame image appears in the dashboard.
8. Officer account can mark a violation as resolved.
9. Admin account can manage sites and workers.

## Useful Commands

Check changed files:

```powershell
git status
```

Push future updates:

```powershell
git add .
git commit -m "Update deployment configuration"
git push origin main
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

If Render build fails:

- Open Render service logs.
- Confirm Dockerfile path is exactly `backend.Dockerfile`.
- Confirm `requirements-backend.txt` exists on GitHub.

If backend says database connection failed:

- Check `DATABASE_URL` in Render.
- Make sure your Supabase password is inside the URL.
- Make sure there are no square brackets around the password.

If Streamlit cannot connect to backend:

- Open the Streamlit app settings.
- Check the secret name is exactly `BACKEND_API_URL`.
- Make sure the URL starts with `https://`.
- Open Render `/health` once to wake the backend.

If violation images do not show:

- Make sure you pushed the updated `ml_pipeline/backend_client.py`.
- Run the local pipeline again after pulling the latest code.
- Old records may only contain local filenames; new records should contain base64 image data.

If Supabase SQL fails:

- Run `001_init_schema.sql` first.
- Run `002_seed_defaults.sql` second.
- Do not run both files at the same time.
