import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import AdminUser, Slip, BatchRecord, VerificationLog
from app.security import hash_password

from app.routes.auth_routes import router as auth_router
from app.routes.verifier_routes import router as verifier_router
from app.routes.generator_routes import router as generator_router
from app.routes.admin_routes import router as admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    # 1. Initialize DB tables
    Base.metadata.create_all(bind=engine)

    # 2. Seed default admin account if not already created
    db = SessionLocal()
    try:
        existing_admin = db.query(AdminUser).first()
        if not existing_admin:
            default_admin = AdminUser(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                is_active=True
            )
            db.add(default_admin)
            db.commit()
            print(f"[INIT] Created default admin account: '{settings.DEFAULT_ADMIN_USERNAME}'")
        else:
            print(f"[INIT] Admin account verified: '{existing_admin.username}'")
    finally:
        db.close()

    yield

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Smart QR Student Slip Generator & Authentication System",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(auth_router)
app.include_router(verifier_router)
app.include_router(generator_router)
app.include_router(admin_router)

# Custom 404 / 500 handlers
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Not Found", "detail": str(exc.detail if hasattr(exc, "detail") else "Resource not found")})
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head><title>404 - Page Not Found</title>
        <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body class="bg-slate-50 flex items-center justify-center min-h-screen font-sans">
            <div class="text-center p-8 bg-white rounded-2xl shadow-sm border border-slate-200 max-w-md mx-auto">
                <div class="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">404</div>
                <h1 class="text-2xl font-bold text-slate-800 mb-2">Page Not Found</h1>
                <p class="text-slate-500 mb-6">The page or slip resource you are looking for does not exist.</p>
                <a href="/dashboard" class="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                    Return to Dashboard
                </a>
            </div>
        </body>
        </html>
        """,
        status_code=404
    )
