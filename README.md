---
title: PPE Backend API
emoji: 🦺
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# Real-Time AI-Powered PPE Compliance & Verification System

This is a comprehensive, full-stack, real-time AI-Powered Personal Protective Equipment (PPE) Compliance and Violation Logging Web System. Built as a **Final Year Project (FYP)**, the system integrates a real-time computer vision detection pipeline with a robust FastAPI backend and an interactive Streamlit dashboard to automatically detect, log, and manage workplace safety violations.

---

## System Architecture Overview

The system consists of three fully integrated core components:
1. **Backend REST API (FastAPI + PostgreSQL):** Handles user authentication (JWT), registers monitoring sites, keeps track of site-specific PPE requirements, and logs violation events and database records.
2. **Interactive Management Dashboard (Streamlit):** Provides real-time statistics, violation tables with saved image frames, a resolution manager for safety officers, and worker registration.
3. **Computer Vision ML Pipeline (YOLOv8 + OpenCV):** Takes camera/video feeds, performs real-time person tracking and PPE detection, evaluates compliance rules, and dynamically logs events to the backend with automated deduplication.

---

## 🤖 Integrated ML Pipeline Core Features

The ML pipeline is fully integrated into this repository under `/ml_pipeline` and includes advanced features developed for maximum real-world reliability:

*   ** Optimized Real-Time Video Display:** Runs a frame-skipping rendering engine with drawing-action caching. The heavy YOLO models run on key frames, while intermediate frames render cached boxes, delivering a smooth **30+ FPS real-time playback** on CPU.
*   ** Instantaneous Red Bounding Boxes:** The moment a worker violates any safety rule, their bounding box immediately turns **RED** on-screen and lists missing items, keeping display responsiveness 100% instantaneous.
*   ** Aggregated Frame-Level Deduplication:** Instead of saving separate images or database logs per-person or per-item, the pipeline aggregates all violations present in a frame and logs/saves the frame exactly **once** per violation event (configurable 30-second grace period).
*   ** High-Confidence Unique Signifier Site Voting:** Dynamic site inference resolves site types (`Chemical Lab`, `Factory`, `Construction Site`, `Warehouse`) instantly by voting on high-confidence unique signifiers (like earmuffs, labcoats, safety shoes) rather than simple percentages.

---

## API Endpoints Summary

POST   /auth/login              → Get JWT token
GET    /sites/                  → List all sites
POST   /sites/                  → Create site (admin)
PUT    /sites/{id}              → Update site (admin, non-default)
DELETE /sites/{id}              → Delete site (admin, non-default)
GET    /workers/                → List workers (admin)
POST   /workers/                → Register worker (admin)
PUT    /workers/{id}            → Update worker (admin)
DELETE /workers/{id}            → Remove worker (admin)
POST   /detection-event/        → Log violation event (ML pipeline)
POST   /violation/              → Log missing PPE item (ML pipeline)
GET    /violations/             → List violations (with filters)
PUT    /violations/{id}/resolve → Resolve a violation
GET    /dashboard/stats/        → Aggregated stats

---

## Frontend Dashboard Pages

| Page | Access | Description |
|---|---|---|
| Overview | Admin + Officer | Stats cards, bar chart by site, compliance gauge |
| Live Violations | Admin + Officer | Filterable table, images, resolve button |
| Site Management | Admin only | CRUD sites, configure PPE requirements |
| Worker Management | Admin only | Register workers, upload face photos |

---

## Database Schema 

| Table | Description |
|---|---|
| `users` | Admin & Security Officer accounts |
| `sites` | Monitoring sites (4 defaults protected) |
| `site_requirements` | Required PPE per site |
| `cameras` | CCTV cameras per site |
| `workers` | Registered employees + face embedding (`vector(512)`) |
| `detection_events` | One row per violation event (not every frame) |
| `violations` | One row per missing PPE item per event |

---

## Default Credentials

| Role             | Email                | Password    |
|---|---|---|
| Admin            | admin@ppe.com        | admin123    |
| Security Officer | officer@ppe.com      | officer123  |

> Requires Changing before any real deployment.

---

## 📁 Repository Structure

```text
PPE_WebApp_System/
├── backend/               # FastAPI REST API (JWT auth, routes, schemas)
├── frontend/              # Streamlit dashboard interface (Overview, Live Violations, Admin Pages)
├── database/              # SQL migrations & seeding scripts
├── ml_pipeline/           # Deep Learning Pipeline
│   ├── models/            # Trained YOLOv8 models (custom ppe_yolov8m_best.pt included!)
│   ├── test_videos/       # Demo video clips (demo.mp4)
│   ├── compliance.py      # Aggregation, deduplication, and site voting engines
│   ├── model_loader.py    # YOLOv8 wrappers
│   ├── main.py            # Main real-time pipeline execution loop
│   └── config.yaml        # Main ML configuration
├── models/                # Basic YOLO person tracking model (yolov8n.pt)
├── saved_violations/      # Destination for saved violation frames (ignored by Git)
├── .gitignore             # Production-grade git exclusion file
├── requirements.txt       # Combined project dependency manifest
└── .env.example           # Shared environment configurations
```

---

## Setup & Execution Guide (For Team Members)

Follow these steps to set up and run the entire full-stack system on a new machine.

### Prerequisites
*   **Python 3.9+** installed.
*   **Docker Desktop** (Required to run the PostgreSQL database locally).
*   **Git** installed.

---

### 💻 Step-by-Step Installation

#### **Step 1: Clone the Repository & Enter Folder**
```bash
git clone https://github.com/Tehreemirfan123/PPE_WebApp_System.git
cd PPE_WebApp_System
```

#### **Step 2: Create a Local Virtual Environment**
```bash
# Create environment
python -m venv venv

# Activate on Windows (Command Prompt)
venv\Scripts\activate
# OR Activate on Windows (PowerShell)
.\venv\Scripts\activate
# OR Activate on Mac/Linux
source venv/bin/activate
```

#### **Step 3: Install Required Dependencies**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### **Step 4: Set Up Local Environment Variables**
Copy the template `.env.example` file to a new file named `.env`:
```bash
# Windows
copy .env.example .env
# Mac/Linux
cp .env.example .env
```
*(You do not need to modify the `.env` contents for local testing; default ports and credentials are pre-configured.)*

#### **Step 5: Launch the PostgreSQL Database Container**
Make sure Docker Desktop is open and run:
```bash
docker-compose up -d db
```
*This automatically sets up a PostgreSQL instance with pgvector support on host port **`5433`** (mapped internally from `5432` to prevent conflicts with native local PostgreSQL servers) and seeds your database with default user accounts, sites, and default PPE requirements.*

---

### Running the Full-Stack Application

To test the system end-to-end, you need to run **three services simultaneously** in separate terminal windows (make sure your virtual environment is active in all of them):

#### **Window 1: Start the FastAPI Backend**
```bash
# Run from the root directory:
uvicorn backend.main:app --reload
```
*   **Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Backend Server URL:** `http://127.0.0.1:8000`

#### **Window 2: Start the Streamlit Dashboard**
```bash
# Run in a separate terminal:
streamlit run frontend/app.py
```
*   **Dashboard URL:** [http://localhost:8501](http://localhost:8501)
*   **Default Login Credentials:**
    *   **Security Officer:** email: `officer@ppe.com` | password: `officer123`
    *   **Administrator:** email: `admin@ppe.com` | password: `admin123`

#### **Window 3: Start the Real-Time ML Detection Pipeline**
```bash
# Run in a third terminal:
python ml_pipeline/main.py
```
*   **Automatic Topmost Pop-up:** Running this script will automatically initialize the YOLO models, authenticate with the FastAPI backend, and **instantly pop up the OpenCV video monitor topmost** in front of all other windows!
*   **To Exit Video Monitoring:** Press the **`q`** key while focused on the video window to safely close it and print execution compliance statistics.

---

## System Default Requirements per Site

| Site Type | Required Equipment | Custom YOLO class mappings |
|---|---|---|
| **Construction Site** | Helmet, Safety Vest, Gloves, Boots | `hardhat`, `safety_vest`, `gloves`, `safety_shoes` |
| **Chemical Lab** | Lab Coat, Goggles, Gloves, Face Mask | `labcoat`, `goggles`, `gloves`, `face_mask` |
| **Factory** | Helmet, Safety Vest, Gloves, Earmuffs | `hardhat`, `safety_vest`, `gloves`, `earmuffs` |
| **Warehouse** | Helmet, Safety Vest, Gloves | `hardhat`, `safety_vest`, `gloves` |

---

## Verification & Running Tests
To verify backend functionality and integrity:
```bash
pytest backend/tests/ -v
```

To run a verification script for all ML pipeline model linkages:
```bash
python test_ml_pipeline.py
```
