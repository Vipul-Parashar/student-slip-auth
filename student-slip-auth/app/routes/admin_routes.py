import csv
import io
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Query, Form, status
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.config import settings
from app.database import get_db
from app.auth import require_admin_html, require_admin
from app.models import Slip, VerificationLog, AdminUser, BatchRecord
from app.qr_verifier import toggle_slip_revocation, mark_slip_redeemed
from app.security import hash_password, verify_password
from app.schemas import RevokeSlipRequest, RedeemSlipRequest

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

@router.get("/", response_class=HTMLResponse)
async def home_redirect(request: Request, admin = Depends(require_admin_html)):
    """Root redirect to dashboard."""
    return HTMLResponse("<script>window.location.href='/dashboard';</script>")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    admin = Depends(require_admin_html),
    db: Session = Depends(get_db)
):
    """SaaS Dashboard with key metrics, recent slips, and scan activity."""
    # Metric counts
    total_slips = db.query(Slip).count()
    active_slips = db.query(Slip).filter(Slip.status == "ACTIVE", Slip.is_redeemed == False).count()
    redeemed_slips = db.query(Slip).filter(Slip.is_redeemed == True).count()
    revoked_slips = db.query(Slip).filter(Slip.status == "REVOKED").count()
    
    total_scans = db.query(VerificationLog).count()
    genuine_scans = db.query(VerificationLog).filter(VerificationLog.result == "GENUINE").count()
    fake_scans = db.query(VerificationLog).filter(VerificationLog.result == "INVALID").count()

    # Recent slips
    recent_slips = db.query(Slip).order_by(Slip.created_at.desc()).limit(8).all()

    # Recent verification attempts
    recent_logs = db.query(VerificationLog).order_by(VerificationLog.timestamp.desc()).limit(8).all()

    # Recent batches
    recent_batches = db.query(BatchRecord).order_by(BatchRecord.created_at.desc()).limit(4).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "title": "Dashboard",
            "admin": admin,
            "active_page": "dashboard",
            "stats": {
                "total_slips": total_slips,
                "active_slips": active_slips,
                "redeemed_slips": redeemed_slips,
                "revoked_slips": revoked_slips,
                "total_scans": total_scans,
                "genuine_scans": genuine_scans,
                "fake_scans": fake_scans,
            },
            "recent_slips": recent_slips,
            "recent_logs": recent_logs,
            "recent_batches": recent_batches
        }
    )

@router.get("/manage", response_class=HTMLResponse)
async def manage_slips_page(
    request: Request,
    q: Optional[str] = Query(None),
    status_filter: Optional[str] = Query("ALL"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    admin = Depends(require_admin_html),
    db: Session = Depends(get_db)
):
    """Manage generated student QR slips: search, status filter, revocation, and redemption."""
    query = db.query(Slip)

    # Search filter
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(Slip.slip_id.like(term), Slip.batch_id.like(term), Slip.notes.like(term)))

    # Status filter
    if status_filter == "ACTIVE":
        query = query.filter(Slip.status == "ACTIVE", Slip.is_redeemed == False)
    elif status_filter == "REDEEMED":
        query = query.filter(Slip.is_redeemed == True)
    elif status_filter == "REVOKED":
        query = query.filter(Slip.status == "REVOKED")

    total_items = query.count()
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    slips = query.order_by(Slip.created_at.desc()).offset(offset).limit(per_page).all()

    return templates.TemplateResponse(
        request=request,
        name="manage.html",
        context={
            "request": request,
            "title": "Manage QR Codes",
            "admin": admin,
            "active_page": "manage",
            "slips": slips,
            "total_items": total_items,
            "current_page": page,
            "total_pages": total_pages,
            "per_page": per_page,
            "q": q or "",
            "status_filter": status_filter
        }
    )

@router.post("/api/slips/revoke")
async def api_toggle_revoke(
    data: RevokeSlipRequest,
    admin = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Revoke or reactivate a slip."""
    slip = db.query(Slip).filter(Slip.slip_id == data.slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Slip not found.")

    # Toggle revocation
    new_state = (slip.status != "REVOKED")
    success, msg, updated = toggle_slip_revocation(
        db=db,
        slip_id=data.slip_id,
        revoke=new_state,
        reason=data.reason
    )
    return JSONResponse(content={"success": success, "message": msg, "new_status": updated.status})

@router.post("/api/slips/redeem")
async def api_admin_redeem(
    data: RedeemSlipRequest,
    admin = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin action to mark a slip as redeemed."""
    success, msg, slip = mark_slip_redeemed(
        db=db,
        slip_id=data.slip_id,
        redeemed_by=f"Admin ({admin.username})",
        notes=data.notes
    )
    if not success:
        return JSONResponse(status_code=400, content={"success": False, "message": msg})
    return JSONResponse(content={"success": True, "message": msg})

@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    filter_result: Optional[str] = Query("ALL"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=10, le=100),
    admin = Depends(require_admin_html),
    db: Session = Depends(get_db)
):
    """Verification History audit logs."""
    query = db.query(VerificationLog)
    if filter_result and filter_result != "ALL":
        query = query.filter(VerificationLog.result == filter_result)

    total_logs = query.count()
    total_pages = max(1, (total_logs + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    logs = query.order_by(VerificationLog.timestamp.desc()).offset(offset).limit(per_page).all()

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "request": request,
            "title": "Verification History",
            "admin": admin,
            "active_page": "history",
            "logs": logs,
            "total_logs": total_logs,
            "current_page": page,
            "total_pages": total_pages,
            "filter_result": filter_result
        }
    )

@router.get("/history/export")
async def export_history_csv(
    admin = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Export all verification logs as a CSV file."""
    logs = db.query(VerificationLog).order_by(VerificationLog.timestamp.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "Slip ID", "Verification Result", "Details", "Client IP", "User Agent", "Payload Snippet"])

    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "",
            log.slip_id or "N/A",
            log.result,
            log.details or "",
            log.ip_address or "",
            log.user_agent or "",
            log.scanned_payload_snippet or ""
        ])

    csv_data = output.getvalue()
    filename = f"Verification_History_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    admin = Depends(require_admin_html),
    db: Session = Depends(get_db)
):
    """Application & Security settings."""
    db_size_kb = 0
    db_path = settings.DATA_DIR / "slips.db"
    if db_path.exists():
        db_size_kb = round(os.path.getsize(db_path) / 1024, 1)

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "request": request,
            "title": "Settings",
            "admin": admin,
            "active_page": "settings",
            "verify_base_url": settings.VERIFY_BASE_URL,
            "db_size_kb": db_size_kb,
            "db_path": str(db_path),
            "rate_limit": settings.RATE_LIMIT_PER_MINUTE
        }
    )

@router.post("/api/settings/password")
async def api_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    admin: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Change admin password securely."""
    if not verify_password(current_password, admin.password_hash):
        return JSONResponse(status_code=400, content={"success": False, "message": "Incorrect current password."})
    if len(new_password) < 8:
        return JSONResponse(status_code=400, content={"success": False, "message": "New password must be at least 8 characters long."})

    admin.password_hash = hash_password(new_password)
    db.commit()
    return JSONResponse(content={"success": True, "message": "Admin password updated successfully."})

@router.post("/api/settings/base-url")
async def api_update_base_url(
    base_url: str = Form(...),
    admin: AdminUser = Depends(require_admin)
):
    """Update verification base URL."""
    clean_url = base_url.strip().rstrip("/")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        return JSONResponse(status_code=400, content={"success": False, "message": "URL must start with http:// or https://"})
    settings.VERIFY_BASE_URL = clean_url
    return JSONResponse(content={"success": True, "message": f"Verification base URL updated to: {clean_url}"})

@router.get("/api/backup/download")
async def api_download_backup(
    admin: AdminUser = Depends(require_admin)
):
    """Create on-demand SQLite database backup and download."""
    db_file = settings.DATA_DIR / "slips.db"
    if not db_file.exists():
        raise HTTPException(status_code=404, detail="Database file not found.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"slips_backup_{timestamp}.db"
    backup_path = settings.BACKUP_DIR / backup_filename

    # Safely copy database file
    shutil.copy2(db_file, backup_path)

    return FileResponse(
        path=str(backup_path),
        media_type="application/octet-stream",
        filename=backup_filename
    )
