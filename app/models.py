from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Slip(Base):
    """Represents a generated student slip QR record."""
    __tablename__ = "slips"

    id = Column(Integer, primary_key=True, index=True)
    slip_id = Column(String(64), unique=True, index=True, nullable=False)
    batch_id = Column(String(64), index=True, nullable=True)
    
    # Store SHA-256 hash of token to prevent recovery even if DB is compromised
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    
    # Status: 'ACTIVE', 'REVOKED'
    status = Column(String(20), default="ACTIVE", index=True, nullable=False)
    
    # Redemption details (one-time usage tracking)
    is_redeemed = Column(Boolean, default=False, index=True, nullable=False)
    redeemed_at = Column(DateTime, nullable=True)
    redeemed_by = Column(String(100), nullable=True)
    
    # Revocation details
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=utcnow, index=True, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationship to verification logs
    logs = relationship("VerificationLog", back_populates="slip", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "slip_id": self.slip_id,
            "batch_id": self.batch_id,
            "status": self.status,
            "is_redeemed": self.is_redeemed,
            "redeemed_at": self.redeemed_at.isoformat() if self.redeemed_at else None,
            "redeemed_by": self.redeemed_by,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_reason": self.revoked_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "notes": self.notes,
        }

class VerificationLog(Base):
    """Audit log of every QR verification attempt."""
    __tablename__ = "verification_logs"

    id = Column(Integer, primary_key=True, index=True)
    slip_id = Column(String(64), ForeignKey("slips.slip_id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Result: 'GENUINE', 'INVALID', 'REVOKED', 'ALREADY_USED'
    result = Column(String(30), nullable=False, index=True)
    details = Column(String(255), nullable=True)
    scanned_payload_snippet = Column(String(255), nullable=True)
    
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=utcnow, index=True, nullable=False)

    slip = relationship("Slip", back_populates="logs")

    def to_dict(self):
        return {
            "id": self.id,
            "slip_id": self.slip_id,
            "result": self.result,
            "details": self.details,
            "scanned_payload_snippet": self.scanned_payload_snippet,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

class AdminUser(Base):
    """Admin user account for portal management."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

class BatchRecord(Base):
    """Record of generated QR batches for easy download & auditing."""
    __tablename__ = "batch_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(64), unique=True, index=True, nullable=False)
    batch_name = Column(String(128), nullable=False)
    count = Column(Integer, nullable=False)
    prefix = Column(String(32), default="Slip_")
    start_index = Column(Integer, default=1)
    end_index = Column(Integer, default=1)
    zip_filename = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
