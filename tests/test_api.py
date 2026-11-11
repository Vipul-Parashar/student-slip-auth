import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import AdminUser, Slip
from app.security import hash_password

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Ensure default admin exists
    admin = db.query(AdminUser).filter(AdminUser.username == "admin").first()
    if not admin:
        admin = AdminUser(
            username="admin",
            password_hash=hash_password("AdminPass@2026"),
            is_active=True
        )
        db.add(admin)
        db.commit()
    db.close()
    yield

def test_login_flow():
    """Test admin authentication."""
    # Invalid password
    resp = client.post("/login", data={"username": "admin", "password": "wrongpassword"}, follow_redirects=False)
    assert resp.status_code == 400

    # Valid password
    resp = client.post("/login", data={"username": "admin", "password": "AdminPass@2026"}, follow_redirects=False)
    assert resp.status_code == 302
    assert "slip_auth_session" in resp.cookies

def test_api_verify_endpoint():
    """Test POST /api/verify."""
    # First generate a batch or insert a slip
    db = SessionLocal()
    from app.qr_generator import generate_slip_batch
    batch = generate_slip_batch(db, count=5, prefix="APITest_")
    db.close()

    slip_id = batch["sample_ids"][0]
    payload = f"http://localhost:8000/verify?id={slip_id}"

    resp = client.post("/api/verify", json={"payload": payload})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "GENUINE"
    assert data["slip_id"] == slip_id

    # Test invalid QR
    resp_fake = client.post("/api/verify", json={"payload": "http://localhost:8000/verify?id=NonExistent_999"})
    assert resp_fake.status_code == 200
    data_fake = resp_fake.json()
    assert data_fake["status"] == "INVALID"

def test_api_redeem_endpoint():
    """Test POST /api/redeem."""
    db = SessionLocal()
    from app.qr_generator import generate_slip_batch
    batch = generate_slip_batch(db, count=1, prefix="RedeemTest_")
    slip_id = batch["sample_ids"][0]
    db.close()

    resp = client.post("/api/redeem", json={"slip_id": slip_id, "notes": "Ballot received"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Subsequent verification must return ALREADY_USED
    v_resp = client.post("/api/verify", json={"payload": f"http://localhost:8000/verify?id={slip_id}"})
    assert v_resp.json()["status"] == "ALREADY_USED"
