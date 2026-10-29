# 🌟 InternTrack — Internship Management & Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Bootstrap](https://img.shields.io/badge/UI-Bootstrap%205.3-7952B3?logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Tests](https://img.shields.io/badge/Tests-78%20Passing-success)]()

**InternTrack** is a modern, enterprise-grade web application designed to streamline and monitor the end-to-end academic internship lifecycle. It bridges the gap between **Students**, **Faculty Mentors**, and **Placement Administrators** with real-time tracking, dynamic timelines, multi-criteria evaluations, and exportable analytics reports.

---

## 🚀 Key Features

### 🎓 1. Student Portal
* **Dashboard & KPI Overview**: Real-time progress bar, milestone countdowns, document verification status, and notification alerts.
* **Internship Registration**: Submit corporate placement details (role, mentor info, duration, work mode).
* **Interactive Timeline**: Step-by-step milestone progression (Registration &rarr; Approval &rarr; Weekly Logs &rarr; Document Verification &rarr; Evaluation &rarr; Completion).
* **Weekly Progress Logging**: Submit and edit weekly hour logs, tasks completed, skills acquired, and challenges faced.
* **Document Vault**: Upload and replace required documents (*Offer Letter, Joining Letter, ID Proof, Weekly Report, Final Report, Completion Certificate*) with format and size validation.
* **Faculty Evaluation**: Real-time viewing of scorecards and comprehensive faculty remarks upon internship completion.
* **Profile Photo BLOB Storage**: Upload profile pictures stored directly as binary data (`db.LargeBinary` / SQLite BLOB) in the database.

### 👨‍🏫 2. Faculty Portal
* **Action Dashboard**: Cohort tracking, pending placement approvals, active internships, and pending evaluations.
* **Placement Approvals**: Review and approve student registrations with automatic timeline and deadline generation.
* **Cohort Directory**: Filter and search students with live progress percentages.
* **Document Verification**: Verify or reject student certificates with instant notification dispatch.
* **Weekly Report Reviews**: Grade weekly logs and post actionable feedback comments.
* **5-Criterion Rubric Evaluation**: Grade students on *Technical Skills, Communication, Punctuality, Work Quality,* and *Discipline* (0–10 scale).

### 🏛️ 3. Administrator Console & Analytics Engine
* **Executive Dashboard**: Institutional placement rate, department distributions, active vs. completed cohorts, top recruiting companies.
* **Complete CRUD Control**: Add, edit, deactivate, or delete student profiles, company recruiter profiles, and placement records.
* **Analytics & Report Generation**: Filter by department/status and export institutional records in **CSV** and **Enterprise PDF** (with two-pass numbered `Page X of Y` headers/footers via ReportLab).

### 🔒 4. Security & Architecture
* **Role-Based Access Control (RBAC)**: Secure route protection via `@login_required` and `@role_required`.
* **Path-Traversal Protected Uploads**: Secure document serving restricted by role and ownership.
* **HTTP Security Hardening**: Strict CSP, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and secure session cookies.
* **Responsive Dark Glassmorphic Design**: Modern UI aesthetic built with responsive Bootstrap 5 and vanilla CSS.

---

## 🛠️ Project Structure

```
minor project/
├── .vscode/                    # VS Code launch & settings configuration
│   ├── launch.json             # F5 Debug configuration for Flask & Tests
│   ├── settings.json           # VS Code workspace settings
│   └── extensions.json         # Recommended extensions
├── database/                   # SQLite database configuration & storage
│   ├── db.py                   # SQLAlchemy initialization & PRAGMA rules
│   └── interntrack_v2.db       # SQLite local database
├── models/                     # Database Models (SQLAlchemy ORM)
│   ├── user.py                 # User, Student, Faculty models
│   ├── company.py              # Company model
│   ├── internship.py           # Internship model
│   ├── document.py             # Document management model
│   ├── timeline.py             # Milestone timeline model
│   ├── report.py               # Weekly progress log model
│   ├── deadline.py             # Deadline countdown model
│   ├── evaluation.py           # Rubric evaluation model
│   └── notification.py         # User alerts model
├── routes/                     # Application Blueprints
│   ├── auth.py                 # Authentication & profile routes
│   ├── student.py              # Student portal routes
│   ├── faculty.py              # Faculty portal routes
│   ├── admin.py                # Admin console & CRUD routes
│   ├── main.py                 # Landing page route
│   └── decorators.py           # RBAC decorators (@role_required)
├── services/                   # Business Services
│   └── report_service.py       # CSV & ReportLab PDF generation engine
├── static/                     # Static Assets
│   ├── css/style.css           # Glassmorphism dark-mode styles
│   └── js/main.js              # Client-side validation & interactivity
├── templates/                  # Jinja2 HTML Templates
│   ├── admin/                  # Admin portal views
│   ├── faculty/                # Faculty portal views
│   ├── student/                # Student portal views
│   ├── errors/                 # 403, 404, 500 error pages
│   ├── base.html               # Base layout with navbar & notifications
│   ├── index.html              # Landing page
│   ├── login.html              # Login view
│   ├── register.html           # Multi-role registration view
│   └── profile.html            # Profile management view
├── uploads/                    # Secure student document storage
├── app.py                      # Flask Application Factory & Entrypoint
├── config.py                   # Environment configuration
├── requirements.txt            # Python dependencies
├── seed_db.py                  # Database Seeder with demo accounts
├── view_database.py            # SQLite database records viewer CLI
├── run.bat                     # Windows one-click launcher
├── run.sh                      # Linux/macOS launcher
└── README.md                   # Project documentation
```

---

## 💻 Quick Start Guide

### Prerequisites
* Python 3.9 or higher installed
* VS Code (recommended) or any modern terminal / IDE

### 1. Open in VS Code
Open the project directory inside VS Code:
```bash
code .
```

### 2. Create and Activate Virtual Environment (Optional but recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Seed Initial Demo Data (Pre-configured)
To populate the database with sample users, companies, internships, and reports:
```bash
python seed_db.py
```

### 5. Run the Application

#### Option A — Direct Command:
```bash
python app.py
```

#### Option B — In VS Code:
* Press **`F5`** or go to **Run and Debug** (`Ctrl+Shift+D`) &rarr; Select **`Python: InternTrack (Flask App)`** &rarr; Press Play.

#### Option C — Using Helper Script:
* Windows: Double-click or run `run.bat`
* Linux / macOS: Run `./run.sh`

Navigate to **`http://localhost:5000`** in your web browser.

---

## 🔑 Default Demo Accounts

The database comes pre-seeded with the following demo accounts:

| Role | Email | Password | Details |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@interntrack.edu` | `adminpassword123` | Institutional Dean / Admin Console |
| **Faculty Mentor** | `faculty@interntrack.edu` | `facultypassword123` | CS Dept Faculty / Approver & Evaluator |
| **Student (Active)** | `student@interntrack.edu` | `studentpassword123` | Ada Lovelace (Ongoing Internship) |
| **Student (Completed)** | `john@interntrack.edu` | `studentpassword123` | John von Neumann (Evaluated & Completed) |
| **Student (Pending)** | `grace@interntrack.edu` | `studentpassword123` | Grace Hopper (Pending Placement Approval) |

*(You can also register brand new Student or Faculty accounts at `/register`)*

---

## 🧪 Running Automated Tests

The application includes an extensive test suite covering all units, role security, document uploads, reports generation, and full lifecycle execution:

```bash
python -m unittest discover -s . -p "test_*.py"
```

### Test Suite Summary (78/78 Passed):
* `test_auth.py`: Registration, Login, Session handling & RBAC
* `test_db.py`: Foreign key constraints & Cascade deletion
* `test_deadlines.py`: Dynamic due date computation & status tags
* `test_documents.py`: MIME type, file extension, and size validation
* `test_faculty.py`: Faculty approval, feedback & verification
* `test_image_storage.py`: SQLite BLOB profile image storage and streaming
* `test_internship.py`: Registration flow & status lifecycles
* `test_progress.py`: Weekly log creation & editing
* `test_step11_evaluation.py`: 5-metric scoring rubric calculations
* `test_step12_admin.py`: Administrator CRUD & entity management
* `test_step13_analytics.py`: Real-time KPI aggregation
* `test_step14_reports.py`: CSV and ReportLab PDF document export
* `test_step15_security.py`: Path traversal protection & HTTP security headers
* `test_step16_e2e.py`: Complete multi-user end-to-end integration lifecycle
* `test_timeline.py`: Automated milestone sequencing

---

## 📜 License & Acknowledgments
Developed as a Minor Project in Web Application Engineering & Academic Workflow Systems.
Built with Flask, SQLAlchemy, Bootstrap 5, and ReportLab.
