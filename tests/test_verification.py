import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Slip, VerificationLog
from app.security import generate_slip_token, hash_token, create_payload_signature
from app.qr_verifier import verify_slip, mark_slip_redeemed, toggle_slip_revocation

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

def create_sample_slip(db, slip_id="Slip_001"):
    raw_token = generate_slip_token()
    token_hash = hash_token(raw_token)
    sig = create_payload_signature(slip_id, raw_token)
    slip = Slip(
        slip_id=slip_id,
        batch_id="TEST_BATCH",
        token_hash=token_hash,
        status="ACTIVE",
        is_redeemed=False
    )
    db.add(slip)
    db.commit()
    db.refresh(slip)
    url = f"http://localhost:8000/verify?id={slip_id}&token={raw_token}&sig={sig}"
    return slip, raw_token, url

def test_verify_genuine_slip(test_db):
    """Test 1: Genuine slip verifies as GENUINE and scanning does NOT mark it as redeemed."""
    slip, raw_token, verify_url = create_sample_slip(test_db, "Slip_001")

    res = verify_slip(test_db, payload=verify_url, client_ip="127.0.0.1")
    assert res["status"] == "GENUINE"
    assert res["status_code"] == "genuine"
    assert res["title"] == "GENUINE SLIP"
    assert res["message"] == "This slip is officially registered."
    assert res["slip_id"] == "Slip_001"
    assert res["is_redeemed"] is False
    assert res["can_redeem"] is True

    # Ensure merely scanning did NOT mark it as used in DB
    refreshed_slip = test_db.query(Slip).filter(Slip.slip_id == "Slip_001").first()
    assert refreshed_slip.is_redeemed is False

def test_verify_fake_unregistered_slip(test_db):
    """Test 2: Fabricated or unregistered QR code rejected as INVALID."""
    fake_url = "http://localhost:8000/verify?id=Slip_999_FAKECANDIDATE&token=fake123"
    res = verify_slip(test_db, payload=fake_url, client_ip="127.0.0.1")
    assert res["status"] == "INVALID"
    assert res["status_code"] == "invalid"
    assert res["title"] == "INVALID SLIP"
    assert "not registered" in res["message"]

def test_verify_altered_token(test_db):
    """Test 3: Valid Slip ID but forged/altered token rejected as INVALID."""
    slip, raw_token, verify_url = create_sample_slip(test_db, "Slip_002")
    altered_url = f"http://localhost:8000/verify?id=Slip_002&token=counterfeit_token_xyz"
    res = verify_slip(test_db, payload=altered_url, client_ip="127.0.0.1")
    assert res["status"] == "INVALID"
    assert "failed cryptographic authentication" in res["message"]

def test_verify_revoked_slip(test_db):
    """Test 4: Revoked slip returns REVOKED."""
    slip, raw_token, verify_url = create_sample_slip(test_db, "Slip_003")

    # Admin revokes the slip
    success, msg, _ = toggle_slip_revocation(test_db, "Slip_003", revoke=True, reason="Suspected tamper")
    assert success is True

    res = verify_slip(test_db, payload=verify_url, client_ip="127.0.0.1")
    assert res["status"] == "REVOKED"
    assert res["status_code"] == "revoked"
    assert res["title"] == "REVOKED SLIP"
    assert "cancelled by the administrator" in res["message"]

def test_verify_already_redeemed_slip(test_db):
    """Test 5: Explicitly redeemed slip returns ALREADY REDEEMED."""
    slip, raw_token, verify_url = create_sample_slip(test_db, "Slip_004")

    # First check: genuine
    res1 = verify_slip(test_db, payload=verify_url)
    assert res1["status"] == "GENUINE"

    # Proctor marks as redeemed
    succ, msg, _ = mark_slip_redeemed(test_db, "Slip_004", redeemed_by="Mr. Proctor")
    assert succ is True

    # Second check: must report ALREADY REDEEMED with timestamp
    res2 = verify_slip(test_db, payload=verify_url)
    assert res2["status"] == "ALREADY_USED"
    assert res2["status_code"] == "already_used"
    assert res2["title"] == "ALREADY REDEEMED"
    assert res2["is_redeemed"] is True
    assert res2["redeemed_at"] is not None
