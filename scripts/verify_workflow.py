import os
import sys
import zipfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.qr_generator import generate_slip_batch
from app.qr_verifier import verify_slip, mark_slip_redeemed, toggle_slip_revocation

def run_workflow_test():
    db = SessionLocal()
    print("=" * 70)
    print("SMART QR STUDENT SLIP AUTHENTICATION - END-TO-END WORKFLOW VERIFICATION")
    print("=" * 70)

    # 1. Generate 60 QR codes for class of 60 students
    print("[STEP 1] Generating 60 QR codes for class of 60 students...")
    res = generate_slip_batch(db, count=60, prefix="Slip_", batch_name="Grade 10 Monitor Election")
    print(f"         Batch ID: {res['batch_id']}")
    print(f"         ZIP File: {res['zip_filename']}")
    print(f"         Count:    {res['count']}")
    print(f"         Sample IDs: {res['sample_ids'][:5]}")

    # 2. Verify ZIP archive
    print("\n[STEP 2] Inspecting generated ZIP archive...")
    with zipfile.ZipFile(res['zip_filepath'], 'r') as zf:
        names = zf.namelist()
        print(f"         Total files in ZIP: {len(names)} (60 PNGs + 1 MANIFEST.txt)")
        assert len(names) == 61, f"Expected 61 files, got {len(names)}"
        assert "MANIFEST.txt" in names, "MANIFEST.txt missing from ZIP"
        for i in range(res["start_index"], res["end_index"] + 1):
            assert f"Slip_{i:03d}.png" in names, f"Slip_{i:03d}.png missing from ZIP"
    print("         [PASS] ZIP archive structure is 100% valid.")

    # 3. Test genuine verification
    first_slip_id = res['sample_ids'][0]
    print(f"\n[STEP 3] Verifying genuine slip: '{first_slip_id}'...")
    gen_res = verify_slip(db, payload=f"http://localhost:8000/verify?id={first_slip_id}", client_ip="127.0.0.1")
    print(f"         Status:  {gen_res['status']}")
    print(f"         Title:   {gen_res['title']}")
    print(f"         Message: {gen_res['message']}")
    assert gen_res['status'] == "GENUINE"
    assert gen_res['is_redeemed'] is False
    print("         [PASS] Genuine slip officially confirmed.")

    # 4. Ensure scanning did not mark slip as redeemed
    print("\n[STEP 4] Verifying scan did NOT automatically consume slip...")
    from app.models import Slip
    slip_in_db = db.query(Slip).filter(Slip.slip_id == first_slip_id).first()
    assert slip_in_db.is_redeemed is False, "Slip should not be marked as redeemed merely by scanning!"
    print("         [PASS] Slip remains unredeemed and available.")

    # 5. Test fake / fabricated QR
    print("\n[STEP 5] Testing fake / fabricated QR code...")
    fake_res = verify_slip(db, payload="http://localhost:8000/verify?id=Slip_FAKE_FORGED_999", client_ip="127.0.0.1")
    print(f"         Status:  {fake_res['status']}")
    print(f"         Title:   {fake_res['title']}")
    print(f"         Message: {fake_res['message']}")
    assert fake_res['status'] == "INVALID"
    print("         [PASS] Fake QR code rejected with INVALID status.")

    # 6. Test revocation
    print(f"\n[STEP 6] Revoking slip: '{first_slip_id}'...")
    toggle_slip_revocation(db, first_slip_id, revoke=True, reason="Damaged paper slip reported")
    rev_res = verify_slip(db, payload=f"http://localhost:8000/verify?id={first_slip_id}", client_ip="127.0.0.1")
    print(f"         Status:  {rev_res['status']}")
    print(f"         Title:   {rev_res['title']}")
    print(f"         Message: {rev_res['message']}")
    assert rev_res['status'] == "REVOKED"
    print("         [PASS] Revoked slip rejected with REVOKED status.")

    # 7. Reactivate and test one-time redemption
    print(f"\n[STEP 7] Reactivating and redeeming slip: '{first_slip_id}'...")
    toggle_slip_revocation(db, first_slip_id, revoke=False)
    mark_slip_redeemed(db, first_slip_id, redeemed_by="Ballot Inspector")
    red_res = verify_slip(db, payload=f"http://localhost:8000/verify?id={first_slip_id}", client_ip="127.0.0.1")
    print(f"         Status:       {red_res['status']}")
    print(f"         Title:        {red_res['title']}")
    print(f"         Redeemed At:  {red_res['redeemed_at']}")
    assert red_res['status'] == "ALREADY_USED"
    assert red_res['is_redeemed'] is True
    print("         [PASS] Redeemed slip correctly identified as ALREADY REDEEMED.")

    print("\n" + "=" * 70)
    print("ALL 7 CORE SYSTEM VERIFICATIONS PASSED WITH ZERO ERRORS!")
    print("=" * 70)
    db.close()

if __name__ == "__main__":
    run_workflow_test()
