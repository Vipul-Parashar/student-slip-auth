import urllib.parse
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models import Slip, VerificationLog
from app.security import hash_token, verify_payload_signature

def parse_qr_payload(payload: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract slip_id, token, and signature from scanned QR payload.
    Supports:
    - Full URL: http://domain.com/verify?id=Slip_001&token=xyz&sig=abc
    - Query string: id=Slip_001&token=xyz&sig=abc
    - JSON-like or raw string
    """
    payload = payload.strip()
    slip_id = None
    token = None
    sig = None

    if "?" in payload:
        # Full URL or query string
        try:
            parsed = urllib.parse.urlparse(payload)
            qs = urllib.parse.parse_qs(parsed.query)
            slip_id = qs.get("id", [None])[0]
            token = qs.get("token", [None])[0]
            sig = qs.get("sig", [None])[0]
        except Exception:
            pass

    # If not found via URL parser, try regex matching
    if not slip_id:
        m_id = re.search(r'(?:id|slip_id|slip)=([A-Za-z0-9_-]+)', payload, re.IGNORECASE)
        if m_id:
            slip_id = m_id.group(1)
        m_tok = re.search(r'token=([A-Za-z0-9_-]+)', payload, re.IGNORECASE)
        if m_tok:
            token = m_tok.group(1)
        m_sig = re.search(r'sig=([a-fA-F0-9]+)', payload, re.IGNORECASE)
        if m_sig:
            sig = m_sig.group(1)

    # If payload is just the plain Slip ID itself (e.g. "Slip_001")
    if not slip_id and re.match(r'^[A-Za-z0-9_-]{3,64}$', payload):
        slip_id = payload

    return slip_id, token, sig

def verify_slip(
    db: Session,
    payload: str,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify QR payload against the server database.
    Returns structured result for the 4 states:
    - GENUINE
    - INVALID
    - REVOKED
    - ALREADY_USED
    """
    slip_id, token, sig = parse_qr_payload(payload)
    snippet = payload[:120]

    # Helper to log scan attempts
    def log_scan(result: str, details: str, sid: Optional[str] = slip_id):
        log_entry = VerificationLog(
            slip_id=sid,
            result=result,
            details=details,
            scanned_payload_snippet=snippet,
            ip_address=client_ip,
            user_agent=user_agent[:250] if user_agent else None
        )
        db.add(log_entry)
        db.commit()

    # Case 1: Unparseable or empty slip ID
    if not slip_id:
        log_scan("INVALID", "Unable to parse Slip ID from payload", sid=None)
        return {
            "status": "INVALID",
            "status_code": "invalid",
            "title": "INVALID SLIP",
            "message": "This QR code is not registered in our system.",
            "slip_id": None,
            "created_at": None,
            "is_redeemed": False,
            "redeemed_at": None,
            "revoked_at": None,
            "can_redeem": False
        }

    # Query database
    slip = db.query(Slip).filter(Slip.slip_id == slip_id).first()

    # Case 2: Slip not found in database
    if not slip:
        log_scan("INVALID", f"Slip ID '{slip_id}' not found in database", sid=slip_id)
        return {
            "status": "INVALID",
            "status_code": "invalid",
            "title": "INVALID SLIP",
            "message": "This QR code is not registered in our system.",
            "slip_id": slip_id,
            "created_at": None,
            "is_redeemed": False,
            "redeemed_at": None,
            "revoked_at": None,
            "can_redeem": False
        }

    # Case 3: Token verification (if token was in QR payload, verify cryptographic hash)
    if token:
        computed_hash = hash_token(token)
        if computed_hash != slip.token_hash:
            log_scan("INVALID", "Cryptographic token mismatch (counterfeit or tampered QR)", sid=slip_id)
            return {
                "status": "INVALID",
                "status_code": "invalid",
                "title": "INVALID SLIP",
                "message": "This QR code failed cryptographic authentication. It may be altered or counterfeit.",
                "slip_id": slip.slip_id,
                "created_at": None,
                "is_redeemed": False,
                "redeemed_at": None,
                "revoked_at": None,
                "can_redeem": False
            }

    # Case 4: Slip is REVOKED
    if slip.status == "REVOKED":
        log_scan("REVOKED", f"Slip {slip_id} was cancelled by administrator", sid=slip_id)
        return {
            "status": "REVOKED",
            "status_code": "revoked",
            "title": "REVOKED SLIP",
            "message": "This slip has been cancelled by the administrator.",
            "slip_id": slip.slip_id,
            "created_at": slip.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if slip.created_at else None,
            "is_redeemed": slip.is_redeemed,
            "redeemed_at": slip.redeemed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if slip.redeemed_at else None,
            "revoked_at": slip.revoked_at.strftime("%Y-%m-%d %H:%M:%S UTC") if slip.revoked_at else None,
            "revoked_reason": slip.revoked_reason or "Revoked by Administrator",
            "can_redeem": False
        }

    # Case 5: Slip was ALREADY REDEEMED
    if slip.is_redeemed:
        redeemed_str = slip.redeemed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if slip.redeemed_at else "Previously redeemed"
        log_scan("ALREADY_USED", f"Slip {slip_id} was already redeemed at {redeemed_str}", sid=slip_id)
        return {
            "status": "ALREADY_USED",
            "status_code": "already_used",
            "title": "ALREADY REDEEMED",
            "message": f"This slip has already been redeemed on {redeemed_str}.",
            "slip_id": slip.slip_id,
            "created_at": slip.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if slip.created_at else None,
            "is_redeemed": True,
            "redeemed_at": redeemed_str,
            "redeemed_by": slip.redeemed_by or "Authorized Staff",
            "revoked_at": None,
            "can_redeem": False
        }

    # Case 6: Slip is GENUINE and ACTIVE
    log_scan("GENUINE", f"Slip {slip_id} verified successfully", sid=slip_id)
    return {
        "status": "GENUINE",
        "status_code": "genuine",
        "title": "GENUINE SLIP",
        "message": "This slip is officially registered.",
        "slip_id": slip.slip_id,
        "batch_id": slip.batch_id,
        "created_at": slip.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if slip.created_at else None,
        "usage_status": "Active (Unused)",
        "is_redeemed": False,
        "redeemed_at": None,
        "revoked_at": None,
        "can_redeem": True
    }

def mark_slip_redeemed(
    db: Session,
    slip_id: str,
    redeemed_by: str = "Admin",
    notes: Optional[str] = None
) -> Tuple[bool, str, Optional[Slip]]:
    """Mark an active slip as redeemed (one-time usage enforcement)."""
    slip = db.query(Slip).filter(Slip.slip_id == slip_id).first()
    if not slip:
        return False, f"Slip ID '{slip_id}' not found.", None
    if slip.status == "REVOKED":
        return False, "Cannot redeem a revoked slip.", slip
    if slip.is_redeemed:
        return False, f"Slip was already redeemed on {slip.redeemed_at}.", slip

    slip.is_redeemed = True
    slip.redeemed_at = datetime.now(timezone.utc)
    slip.redeemed_by = redeemed_by
    if notes:
        slip.notes = (slip.notes or "") + f" | Redemption: {notes}"
    db.commit()
    db.refresh(slip)

    # Log redemption
    log = VerificationLog(
        slip_id=slip.slip_id,
        result="ALREADY_USED",
        details=f"Marked as redeemed by {redeemed_by}",
        scanned_payload_snippet=f"Action: Redeem {slip_id}",
    )
    db.add(log)
    db.commit()

    return True, f"Slip '{slip_id}' successfully marked as redeemed.", slip

def toggle_slip_revocation(
    db: Session,
    slip_id: str,
    revoke: bool = True,
    reason: Optional[str] = None
) -> Tuple[bool, str, Optional[Slip]]:
    """Revoke or restore a slip."""
    slip = db.query(Slip).filter(Slip.slip_id == slip_id).first()
    if not slip:
        return False, f"Slip ID '{slip_id}' not found.", None

    if revoke:
        slip.status = "REVOKED"
        slip.revoked_at = datetime.now(timezone.utc)
        slip.revoked_reason = reason or "Revoked by Administrator"
        msg = f"Slip '{slip_id}' has been revoked."
    else:
        slip.status = "ACTIVE"
        slip.revoked_at = None
        slip.revoked_reason = None
        msg = f"Slip '{slip_id}' has been reactivated to ACTIVE status."

    db.commit()
    db.refresh(slip)
    return True, msg, slip
