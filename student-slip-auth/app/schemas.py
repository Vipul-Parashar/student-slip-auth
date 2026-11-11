from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class GenerateQRRequest(BaseModel):
    count: int = Field(..., ge=1, le=1000, description="Number of unique QR codes to generate (1 to 1000)")
    prefix: str = Field(default="Slip_", max_length=32, description="Prefix for Slip ID, e.g. Slip_ or SLIP-2026-")
    batch_name: Optional[str] = Field(default=None, max_length=128, description="Optional batch description/label")
    notes: Optional[str] = Field(default=None, max_length=255, description="Optional notes for this batch")

class GenerateQRResponse(BaseModel):
    success: bool
    batch_id: str
    count: int
    zip_filename: str
    zip_download_url: str
    slips: List[str]  # sample of generated IDs
    message: str

class VerifyPayloadRequest(BaseModel):
    payload: str = Field(..., description="Scanned QR raw payload string or full verification URL")

class SlipVerificationResult(BaseModel):
    status: str  # 'GENUINE', 'INVALID', 'REVOKED', 'ALREADY_USED'
    title: str
    message: str
    slip_id: Optional[str] = None
    created_at: Optional[str] = None
    status_code: str  # 'genuine', 'invalid', 'revoked', 'already_used'
    is_redeemed: bool = False
    redeemed_at: Optional[str] = None
    revoked_at: Optional[str] = None
    can_redeem: bool = False

class RedeemSlipRequest(BaseModel):
    slip_id: str
    notes: Optional[str] = None

class RevokeSlipRequest(BaseModel):
    slip_id: str
    reason: Optional[str] = "Revoked by Administrator"

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
