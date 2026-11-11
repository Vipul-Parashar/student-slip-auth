from typing import Optional
from fastapi import Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AdminUser
from app.security import read_session_token, verify_password

def get_current_admin_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[AdminUser]:
    """Retrieve logged in admin user if session cookie is present and valid."""
    cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not cookie:
        return None
    session_data = read_session_token(cookie)
    if not session_data or "user_id" not in session_data:
        return None
    user = db.query(AdminUser).filter(
        AdminUser.id == session_data["user_id"],
        AdminUser.is_active == True
    ).first()
    return user

def require_admin(
    request: Request,
    db: Session = Depends(get_db)
) -> AdminUser:
    """Dependency that ensures the user is logged in as an admin for API endpoints."""
    admin = get_current_admin_optional(request, db)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in as an administrator."
        )
    return admin

def require_admin_html(
    request: Request,
    db: Session = Depends(get_db)
) -> AdminUser:
    """Dependency for HTML routes that redirects to /login if unauthenticated."""
    admin = get_current_admin_optional(request, db)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": f"/login?next={request.url.path}"}
        )
    return admin

def authenticate_admin(db: Session, username: str, password: str) -> Optional[AdminUser]:
    """Authenticate admin username and password against database."""
    admin = db.query(AdminUser).filter(AdminUser.username == username.strip()).first()
    if not admin or not admin.is_active:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin
