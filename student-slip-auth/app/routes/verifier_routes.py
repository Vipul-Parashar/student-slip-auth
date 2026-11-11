from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional

from app.config import settings
from app.database import get_db
from app.auth import get_current_admin_optional
from app.qr_verifier import verify_slip, mark_slip_redeemed
from app.schemas import VerifyPayloadRequest, RedeemSlipRequest
from app.security import rate_limiter

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

@router.get("/scan", response_class=HTMLResponse)
async def scanner_page(request: Request, db: Session = Depends(get_db)):
    """Dedicated in-browser QR code scanner page using laptop or mobile camera / image upload."""
    admin = get_current_admin_optional(request, db)
    return templates.TemplateResponse(
        request=request,
        name="scanner.html",
        context={
            "request": request,
            "title": "Scan & Verify Slip",
            "admin": admin,
            "active_page": "scanner"
        }
    )

@router.get("/verify", response_class=HTMLResponse)
async def direct_verify_page(
    request: Request,
    id: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    sig: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Direct landing page when a QR code is scanned via standard mobile phone camera.
    URL format: /verify?id=Slip_001&token=...&sig=...
    """
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "Unknown")

    # Rate limiting protection
    if not rate_limiter.is_allowed(f"verify_{client_ip}"):
        return templates.TemplateResponse(
            request=request,
            name="verify_public.html",
            context={
                "request": request,
                "title": "Verification Rate Limit",
                "result": {
                    "status": "INVALID",
                    "status_code": "invalid",
                    "title": "RATE LIMIT REACHED",
                    "message": "Too many verification requests. Please wait a moment and try again.",
                    "slip_id": id,
                    "can_redeem": False
                },
                "admin": get_current_admin_optional(request, db)
            },
            status_code=429
        )

    # Reconstruct payload
    if id:
        full_url = str(request.url)
        result = verify_slip(db, payload=full_url, client_ip=client_ip, user_agent=user_agent)
    else:
        result = {
            "status": "INVALID",
            "status_code": "invalid",
            "title": "INVALID SLIP",
            "message": "No Slip ID or verification token provided.",
            "slip_id": None,
            "can_redeem": False
        }

    admin = get_current_admin_optional(request, db)
    return templates.TemplateResponse(
        request=request,
        name="verify_public.html",
        context={
            "request": request,
            "title": f"Slip Verification - {id or 'Scan'}",
            "result": result,
            "admin": admin
        }
    )

@router.post("/api/verify")
async def api_verify_slip(
    request: Request,
    payload_data: VerifyPayloadRequest,
    db: Session = Depends(get_db)
):
    """API endpoint called by the camera scanner and upload scanner."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "Unknown")

    if not rate_limiter.is_allowed(f"api_verify_{client_ip}"):
        return JSONResponse(
            status_code=429,
            content={
                "status": "INVALID",
                "status_code": "invalid",
                "title": "RATE LIMIT EXCEEDED",
                "message": "Too many scan attempts. Please wait a moment before scanning again.",
                "can_redeem": False
            }
        )

    result = verify_slip(
        db=db,
        payload=payload_data.payload,
        client_ip=client_ip,
        user_agent=user_agent
    )
    return JSONResponse(content=result)

@router.post("/api/redeem")
async def api_redeem_slip(
    request: Request,
    data: RedeemSlipRequest,
    db: Session = Depends(get_db)
):
    """
    Mark an active slip as redeemed (one-time usage enforcement).
    Accessible to logged-in admin or authorized proctor.
    """
    admin = get_current_admin_optional(request, db)
    redeemer_name = admin.username if admin else "Proctor (Scanner)"

    success, message, slip = mark_slip_redeemed(
        db=db,
        slip_id=data.slip_id,
        redeemed_by=redeemer_name,
        notes=data.notes
    )

    if not success:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": message}
        )

    return JSONResponse(content={
        "success": True,
        "message": message,
        "slip_id": slip.slip_id,
        "redeemed_at": slip.redeemed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if slip.redeemed_at else None,
        "redeemed_by": slip.redeemed_by
    })
