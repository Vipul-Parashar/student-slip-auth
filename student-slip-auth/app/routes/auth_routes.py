from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.config import settings
from app.database import get_db
from app.auth import authenticate_admin, get_current_admin_optional
from app.security import create_session_token, rate_limiter

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    # If already logged in, redirect to dashboard
    admin = get_current_admin_optional(request, db)
    if admin:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    next_url = request.query_params.get("next", "/dashboard")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "title": "Admin Login",
            "next": next_url,
            "error": None
        }
    )

@router.post("/login")
async def process_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/dashboard"),
    db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(f"login_{client_ip}"):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "title": "Admin Login",
                "next": next,
                "error": "Too many login attempts. Please wait a minute before trying again."
            },
            status_code=429
        )

    admin = authenticate_admin(db, username, password)
    if not admin:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "title": "Admin Login",
                "next": next,
                "error": "Invalid username or password. Please verify your credentials."
            },
            status_code=400
        )

    # Issue signed session cookie
    session_payload = {"user_id": admin.id, "username": admin.username}
    token = create_session_token(session_payload)

    target_url = next if next and next.startswith("/") else "/dashboard"
    response = RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG  # True in production HTTPS
    )
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login?msg=logged_out", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME)
    return response
