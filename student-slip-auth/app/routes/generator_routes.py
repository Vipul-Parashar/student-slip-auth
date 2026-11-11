import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.auth import require_admin_html, require_admin, get_current_admin_optional
from app.qr_generator import generate_slip_batch, generate_single_slip_image
from app.schemas import GenerateQRRequest
from app.models import BatchRecord, Slip

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

@router.get("/generate", response_class=HTMLResponse)
async def generate_page(
    request: Request,
    admin = Depends(require_admin_html),
    db: Session = Depends(get_db)
):
    """Dedicated QR Generator page for creating unique student slips in batches."""
    recent_batches = db.query(BatchRecord).order_by(BatchRecord.created_at.desc()).limit(5).all()
    total_slips = db.query(Slip).count()

    return templates.TemplateResponse(
        request=request,
        name="generate.html",
        context={
            "request": request,
            "title": "Generate QR Codes",
            "admin": admin,
            "active_page": "generate",
            "recent_batches": recent_batches,
            "total_slips": total_slips,
            "default_base_url": settings.VERIFY_BASE_URL
        }
    )

@router.post("/api/generate")
async def api_generate_batch(
    request: Request,
    req_data: GenerateQRRequest,
    admin = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Generate unique QR codes for student slips:
    1. Generates count unique QR codes.
    2. Registers all IDs in the database.
    3. Creates individual PNG images (e.g. Slip_001.png).
    4. Creates ZIP archive named Student_QR_Codes.zip.
    5. Returns download links.
    """
    try:
        # Determine effective base URL from request headers if default is localhost
        base_url = str(request.base_url).rstrip("/")
        if settings.VERIFY_BASE_URL and "localhost" not in settings.VERIFY_BASE_URL:
            base_url = settings.VERIFY_BASE_URL.rstrip("/")

        result = generate_slip_batch(
            db=db,
            count=req_data.count,
            prefix=req_data.prefix or "Slip_",
            batch_name=req_data.batch_name,
            notes=req_data.notes,
            base_url=base_url
        )

        return JSONResponse(content={
            "success": True,
            "batch_id": result["batch_id"],
            "batch_name": result["batch_name"],
            "count": result["count"],
            "start_index": result["start_index"],
            "end_index": result["end_index"],
            "zip_filename": result["zip_filename"],
            "zip_download_url": f"/download/zip/{result['zip_filename']}",
            "latest_zip_url": "/download/latest-zip",
            "sample_ids": result["sample_ids"],
            "message": f"Successfully generated and registered {result['count']} unique QR slips!"
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error generating QR codes: {str(e)}"}
        )

@router.get("/download/zip/{filename}")
async def download_zip(
    filename: str,
    admin = Depends(require_admin)
):
    """Securely download generated QR codes ZIP file."""
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(filename)
    filepath = settings.ZIP_STORAGE_DIR / safe_filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Requested ZIP file was not found.")
    
    return FileResponse(
        path=str(filepath),
        media_type="application/zip",
        filename=safe_filename
    )

@router.get("/download/latest-zip")
async def download_latest_zip(
    admin = Depends(require_admin)
):
    """Download the most recently generated Student_QR_Codes.zip."""
    filepath = settings.ZIP_STORAGE_DIR / "Student_QR_Codes.zip"
    if not filepath.exists():
        # Fallback to most recent batch zip if latest alias doesn't exist
        zips = sorted(settings.ZIP_STORAGE_DIR.glob("*.zip"), key=os.path.getmtime, reverse=True)
        if zips:
            filepath = zips[0]
        else:
            raise HTTPException(status_code=404, detail="No QR ZIP archives generated yet.")

    return FileResponse(
        path=str(filepath),
        media_type="application/zip",
        filename="Student_QR_Codes.zip"
    )

@router.get("/download/qr/{slip_id}")
async def download_single_qr(
    slip_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Download or view a single high-resolution printable QR code card."""
    base_url = str(request.base_url).rstrip("/")
    img = generate_single_slip_image(db, slip_id, base_url=base_url)
    if not img:
        raise HTTPException(status_code=404, detail=f"Slip '{slip_id}' not found.")

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    from fastapi.responses import Response
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={slip_id}.png"}
    )
