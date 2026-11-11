# Smart QR Student Slip Generator & Authentication System

A production-ready full-stack web application that generates unique cryptographically authenticated QR codes for physical student paper slips and validates their authenticity in real-time through camera or image scanning.

---

## 1. Project Objective & Workflow

The system is purpose-built for physical student voting or slip authentication (e.g. Class Monitor Elections):

```
       FRONT OF PHYSICAL SLIP                 BACK OF PHYSICAL SLIP
  +-------------------------------+      +-------------------------------+
  |   CLASS MONITOR ELECTION      |      |  OFFICIAL AUTHENTICATION SLIP |
  |                               |      |        +-------------+        |
  |  Candidate Name:              |      |        | [QR CODE]   |        |
  |  [ Student writes choice here]|      |        +-------------+        |
  |                               |      |           Slip_042            |
  |                               |      |  Scan with camera to verify   |
  +-------------------------------+      +-------------------------------+
```

1. **Generate**: Teacher or admin enters class size (e.g. 60). The server registers 60 unique Slip IDs, generates high-resolution printable PNG cards, and packs them into a single `Student_QR_Codes.zip`.
2. **Print & Assemble**: The teacher prints the images and attaches one unique QR code to the **back** of each blank physical paper slip.
3. **Student Casts Choice**: Students manually write the monitor candidate name on the **front** of the physical slip.
4. **Authenticate at Ballot Box**: The proctor scans the back QR code using the website scanner on laptop or smartphone. The website instantly checks against the database and confirms whether the slip is genuine before the slip is deposited.

---

## 2. The Four Verification States

Every scanned QR code is verified live against the server database and triggers immediate visual, acoustic (sound chime/buzz), and haptic feedback:

| State | Badge Color | Result Title | Meaning |
| :--- | :--- | :--- | :--- |
| **A. Genuine** | **Green** | `GENUINE SLIP` | Slip ID is officially registered in database and token is valid. Displays Slip ID, issue date, and "Active / Unused" status. |
| **B. Invalid** | **Red** | `INVALID SLIP` | QR code was fabricated, tampered with, forged, or not found in the database. |
| **C. Revoked** | **Red** | `REVOKED SLIP` | Slip was cancelled or invalidated by the administrator. |
| **D. Already Used** | **Orange** | `ALREADY REDEEMED` | Slip was already submitted/scanned. Displays the exact prior redemption timestamp to detect photocopied duplicates! |

> **Note on Paper Photocopy Resistance:** A QR code on paper can theoretically be photocopied. Merely scanning does **not** consume a slip. However, the system includes an authorized **"Mark as Redeemed"** action upon ballot deposit. Once redeemed, any subsequent photocopy presented to the scanner is immediately flagged as **ALREADY REDEEMED** with the exact redemption timestamp!

---

## 3. Technology Stack

- **Backend**: Python 3.10+ with [FastAPI](https://fastapi.tiangolo.com/) and [Uvicorn](https://www.uvicorn.org/)
- **Database**: SQLite (default, zero configuration) with [SQLAlchemy 2.0](https://www.sqlalchemy.org/) ORM. Fully compatible with PostgreSQL.
- **Frontend**: Responsive HTML5, Modern CSS3 (Stripe & Linear design system aesthetic), Vanilla JavaScript (zero npm build step needed).
- **QR Generation**: Python `qrcode` + [Pillow (PIL)](https://pillow.readthedocs.io/) high-resolution 300DPI printable card generator.
- **QR Scanner**: Embedded [html5-qrcode](https://github.com/mebjas/html5-qrcode) (bundled locally for 100% offline capability + camera switch + file upload).
- **Archiving**: Python standard `zipfile` with Deflate compression.
- **Security**: PBKDF2-HMAC-SHA256 password hashing (OWASP standard), SHA-256 token hashing, HMAC-SHA256 signatures, sliding-window rate limiting.

---

## 4. Quick Start (Windows)

### Option A: One-Click Launcher (Recommended)
Double-click `run.bat` in the project root directory. It will automatically:
1. Verify Python installation
2. Create a virtual environment (`venv`) if not present
3. Install required packages
4. Initialize database and default admin account
5. Launch the server at `http://localhost:8000`

### Option B: PowerShell Manual Setup
```powershell
# 1. Open PowerShell in project directory
cd student-slip-auth

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database & admin
python scripts/init_db.py

# 5. Start development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 5. Quick Start (Linux & macOS)

```bash
cd student-slip-auth
chmod +x run.sh scripts/*.py
./run.sh
```

Or using Docker:
```bash
docker compose up --build -d
```

---

## 6. Default Admin Credentials

Upon initial launch, the system automatically creates the default administrator account:

- **Login URL**: `http://localhost:8000/login`
- **Username**: `admin`
- **Password**: `AdminPass@2026`

*(You can change this password anytime in the **Settings** tab!)*

---

## 7. Free Hosting Deployment Instructions

You can host this application completely free on multiple modern platforms:

### A. Deploy to Render (render.com) - Free Tier
1. Fork or push this repository to GitHub.
2. Sign in to [Render](https://render.com) and click **New +** -> **Web Service**.
3. Connect your GitHub repository.
4. Select **Python 3** environment:
   - **Build Command**: `pip install -r requirements.txt && python scripts/init_db.py`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. In **Environment Variables**, add:
   - `SECRET_KEY`: (A random 32-character string)
   - `HMAC_SECRET`: (A random 32-character string)
   - `VERIFY_BASE_URL`: `https://your-app-name.onrender.com`
   - `ADMIN_PASSWORD`: (Your secure custom password)
6. Click **Deploy Web Service**.

> **Render Persistent Storage Note:** Render free web services have ephemeral disks (restarted on redeploys). To keep database records permanently on Render:
> 1. Create a free **PostgreSQL Database** on Render (under New -> PostgreSQL).
> 2. Copy the `Internal Database URL`.
> 3. In your Web Service settings, set `DATABASE_URL` to that postgres URL (e.g. `postgresql://user:pass@host/db`).
> SQLAlchemy will automatically create all tables in Postgres!

### B. Deploy to Railway (railway.app)
1. In Railway, click **New Project** -> **Deploy from GitHub repo**.
2. Railway detects Python automatically.
3. Add a persistent volume mounted at `/app/data` (Settings -> Volumes -> Mount `/app/data`).
4. Set environment variable `VERIFY_BASE_URL` to your Railway generated domain.

### C. Deploy using Docker on Any VPS (Hetzner, DigitalOcean, Oracle Free)
```bash
docker compose up -d
```
All database records and generated ZIP files are saved to named Docker volumes (`slip_data`, `slip_storage`).

---

## 8. Backup and Restore

### On-Demand Backup
Run the backup script anytime or click **Download Database Backup** in the Settings tab:
```bash
python scripts/backup_db.py
```
This writes a timestamped file into `backups/slips_backup_YYYYMMDD_HHMMSS.db`.

### Restore from Backup
```bash
# Auto-restore latest backup:
python scripts/restore_db.py

# Or specify a particular backup file:
python scripts/restore_db.py backups/slips_backup_20261110_180000.db
```

---

## 9. Running Automated Tests

Run the full pytest suite (all 12 automated unit and integration tests):
```bash
python -m pytest -v
```

The automated test suite verifies:
- Generation of 1, 60, and 100 QR codes with zero collisions.
- DB registration of all batch Slip IDs.
- High-resolution Pillow image rendering and cut-border creation.
- ZIP file structure and extraction integrity.
- Immediate genuine verification for valid slips.
- Prevention of auto-redemption during normal scan.
- Rejection of counterfeit, unregistered, or altered QR codes.
- Immediate rejection of revoked codes.
- Accurate detection of already-redeemed slips with timestamps.
- Admin login and API endpoints.

---

## 10. Project File Structure

```
student-slip-auth/
├── app/
│   ├── __init__.py
│   ├── config.py              # Environment settings & directory management
│   ├── database.py            # SQLAlchemy engine & session factory
│   ├── models.py              # Slip, BatchRecord, VerificationLog, AdminUser
│   ├── schemas.py             # Pydantic validation schemas
│   ├── security.py            # PBKDF2 hashing, 256-bit entropy tokens, rate limiter
│   ├── auth.py                # Admin session dependencies & cookies
│   ├── qr_generator.py        # High-res QR cards, cut guides, ZIP bundler
│   ├── qr_verifier.py         # 4-state authenticity engine & audit logger
│   ├── routes/
│   │   ├── auth_routes.py     # Login & logout
│   │   ├── generator_routes.py# Batch generator & ZIP downloads
│   │   ├── verifier_routes.py # Camera scanner & verification API
│   │   └── admin_routes.py    # Dashboard, slip manager, history, settings
│   ├── templates/
│   │   ├── base.html          # Responsive SaaS navigation & layout
│   │   ├── login.html         # Admin login card
│   │   ├── dashboard.html     # Stats metrics, recent slips, live scan feed
│   │   ├── generate.html      # Batch generator form, presets, ZIP trigger
│   │   ├── scanner.html       # Camera scanner, upload dropzone, 4-state modal
│   │   ├── manage.html        # Slip search, revoke toggle, redemption
│   │   ├── history.html       # Audit scan history & CSV export
│   │   ├── settings.html      # Base URL, password update, DB backup
│   │   └── verify_public.html # Direct mobile scan landing page
│   └── static/
│       ├── css/
│       │   └── style.css      # SaaS design system (Stripe/Linear aesthetic)
│       └── js/
│           ├── html5-qrcode.min.js # Bundled offline QR scanner
│           ├── scanner.js     # Camera control, synthesized audio & modals
│           └── generator.js   # Batch progress & preview
├── scripts/
│   ├── init_db.py             # Database creation & admin seeder
│   ├── backup_db.py           # Snapshot backup script
│   └── restore_db.py          # Database restore script
├── tests/
│   ├── test_qr_generator.py   # 1, 60, 100 batch generation tests
│   ├── test_verification.py   # Genuine, Invalid, Revoked, Redeemed tests
│   └── test_api.py            # API client integration tests
├── .env.example               # Template environment configuration
├── .gitignore                 # Version control ignores
├── Dockerfile                 # Container image specification
├── docker-compose.yml         # Container compose definition
├── requirements.txt           # Python package dependencies
├── run.bat                    # One-click Windows launcher
├── run.ps1                    # PowerShell launcher
├── run.sh                     # Linux/macOS launcher
└── README.md                  # Comprehensive documentation
```

---

## 11. Security Model Summary

1. **No Sensitive Data in QR**: QR payloads contain only `slip_id`, an unguessable 256-bit cryptographically random token, and an HMAC-SHA256 signature. No student names or private election data are stored in the QR code.
2. **Server-Side Validation**: A QR code cannot be validated purely client-side; every scan queries the server database. Fabricated or altered QR codes return `INVALID SLIP`.
3. **Database Token Hashing**: Tokens are stored as SHA-256 hashes (`token_hash`), ensuring that even a database leak does not expose raw verification tokens.
4. **Rate Limiting**: Public verify and login endpoints are protected by in-memory rate limiting against brute-force attacks.
5. **Zero External API Dependencies**: Works completely self-hosted without paid external APIs.
