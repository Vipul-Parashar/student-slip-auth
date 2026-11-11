import pytest
import zipfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Slip, BatchRecord
from app.qr_generator import generate_slip_batch, create_slip_qr_card

@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

def test_generate_single_qr_code(test_db):
    """Test generating 1 QR code."""
    res = generate_slip_batch(db=test_db, count=1, prefix="Test1_")
    assert res["success"] is True
    assert res["count"] == 1
    assert len(res["sample_ids"]) == 1
    assert res["sample_ids"][0] == "Test1_001"

    # Verify DB record
    slip = test_db.query(Slip).filter(Slip.slip_id == "Test1_001").first()
    assert slip is not None
    assert slip.status == "ACTIVE"
    assert slip.is_redeemed is False
    assert len(slip.token_hash) == 64  # SHA-256

def test_generate_60_qr_codes(test_db):
    """Test generating exactly 60 QR codes (Class Size requirement)."""
    res = generate_slip_batch(db=test_db, count=60, prefix="Slip_")
    assert res["success"] is True
    assert res["count"] == 60

    # Verify all 60 are in DB
    slips = test_db.query(Slip).filter(Slip.batch_id == res["batch_id"]).all()
    assert len(slips) == 60

    # Ensure every slip ID is unique
    slip_ids = [s.slip_id for s in slips]
    assert len(set(slip_ids)) == 60

    # Ensure every token hash is unique
    token_hashes = [s.token_hash for s in slips]
    assert len(set(token_hashes)) == 60

    # Verify ZIP file exists and contains all 60 PNGs + MANIFEST.txt
    zip_path = Path(res["zip_filepath"])
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path, 'r') as zf:
        namelist = zf.namelist()
        assert "MANIFEST.txt" in namelist
        for i in range(1, 61):
            expected_png = f"Slip_{i:03d}.png"
            assert expected_png in namelist

def test_generate_100_qr_codes(test_db):
    """Test generating 100 QR codes."""
    res = generate_slip_batch(db=test_db, count=100, prefix="BigClass_")
    assert res["success"] is True
    assert res["count"] == 100

    slips = test_db.query(Slip).filter(Slip.batch_id == res["batch_id"]).all()
    assert len(slips) == 100
    assert len(set(s.slip_id for s in slips)) == 100

def test_qr_image_generation():
    """Test creating printable QR card image with Pillow."""
    img = create_slip_qr_card(
        slip_id="Slip_001",
        verification_url="http://localhost:8000/verify?id=Slip_001&token=abc",
        subtitle="OFFICIAL STUDENT SLIP"
    )
    assert img is not None
    assert img.size[0] > 200
    assert img.size[1] > 200
    assert img.mode == "RGB"
