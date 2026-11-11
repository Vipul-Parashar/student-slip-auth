import io
import os
import zipfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Slip, BatchRecord
from app.security import (
    generate_slip_token,
    hash_token,
    create_payload_signature
)

def get_font(size: int, bold: bool = False):
    """Load system font if available, fallback to Pillow scalable default font."""
    font_candidates = [
        # Windows fonts
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        # Linux / Docker fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

def create_slip_qr_card(
    slip_id: str,
    verification_url: str,
    subtitle: str = "OFFICIAL AUTHENTICATION SLIP"
) -> Image.Image:
    """
    Generate a high-resolution, printable QR card image with:
    - Clean white background
    - Crisp high-contrast QR code (Level M error correction)
    - Distinct Slip ID printed prominently below the QR
    - Cut-guide border for easy scissor trimming and attachment to student slips
    """
    # 1. Generate base QR code
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(verification_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_w, qr_h = qr_img.size

    # 2. Dimensions for the printable card
    padding = 30
    header_height = 45
    footer_height = 95
    card_w = qr_w + (padding * 2)
    card_h = qr_h + header_height + footer_height + (padding * 2)

    # 3. Create canvas
    card = Image.new("RGB", (card_w, card_h), color="white")
    draw = ImageDraw.Draw(card)

    # 4. Fonts
    font_header = get_font(size=14, bold=True)
    font_id = get_font(size=26, bold=True)
    font_sub = get_font(size=12, bold=False)

    # 5. Header text
    try:
        bbox_header = draw.textbbox((0, 0), subtitle, font=font_header)
        header_text_w = bbox_header[2] - bbox_header[0]
    except Exception:
        header_text_w = len(subtitle) * 8
    header_x = (card_w - header_text_w) // 2
    header_y = padding + 10
    draw.text((header_x, header_y), subtitle, fill=(100, 116, 139), font=font_header)

    # Header divider line
    line_y = header_y + 25
    draw.line([(padding, line_y), (card_w - padding, line_y)], fill=(226, 232, 240), width=1)

    # 6. Paste QR code in center
    qr_x = padding
    qr_y = line_y + 15
    card.paste(qr_img, (qr_x, qr_y))

    # 7. Prominent Slip ID below QR
    id_y = qr_y + qr_h + 12
    try:
        bbox_id = draw.textbbox((0, 0), slip_id, font=font_id)
        id_text_w = bbox_id[2] - bbox_id[0]
    except Exception:
        id_text_w = len(slip_id) * 14
    id_x = (card_w - id_text_w) // 2
    draw.text((id_x, id_y), slip_id, fill=(15, 23, 42), font=font_id)

    # 8. Sub-caption below Slip ID
    caption = "Scan with camera to authenticate"
    try:
        bbox_cap = draw.textbbox((0, 0), caption, font=font_sub)
        cap_text_w = bbox_cap[2] - bbox_cap[0]
    except Exception:
        cap_text_w = len(caption) * 6
    cap_x = (card_w - cap_text_w) // 2
    cap_y = id_y + 36
    draw.text((cap_x, cap_y), caption, fill=(148, 163, 184), font=font_sub)

    # 9. Clean subtle border around card (cut guide)
    border_margin = 10
    draw.rectangle(
        [(border_margin, border_margin), (card_w - border_margin, card_h - border_margin)],
        outline=(203, 213, 225),
        width=1
    )

    return card

def generate_slip_batch(
    db: Session,
    count: int,
    prefix: str = "Slip_",
    batch_name: Optional[str] = None,
    notes: Optional[str] = None,
    base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate `count` unique QR codes, save to DB, generate PNGs,
    and package everything into a single downloadable ZIP file.
    """
    if count < 1 or count > 1000:
        raise ValueError("Count must be between 1 and 1000")

    # Resolve base URL for QR verification links
    effective_base_url = (base_url or settings.VERIFY_BASE_URL).rstrip("/")

    # Generate unique batch ID
    batch_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_uuid = uuid.uuid4().hex[:6]
    batch_id = f"BATCH_{batch_timestamp}_{batch_uuid}"
    batch_label = batch_name or f"Class Batch {batch_timestamp}"

    # Determine padding width based on count (e.g. 001 for 60, 0001 for 1000)
    pad_width = max(3, len(str(count)))

    # Determine starting index based on existing slips with this prefix
    # So subsequent batches don't overlap in Slip ID if using the same prefix
    existing_count = db.query(Slip).filter(Slip.slip_id.like(f"{prefix}%")).count()
    start_index = existing_count + 1
    end_index = existing_count + count

    # Temporary directory for this batch's images
    batch_qr_dir = settings.QR_STORAGE_DIR / batch_id
    batch_qr_dir.mkdir(parents=True, exist_ok=True)

    generated_slips: List[Slip] = []
    generated_filenames: List[str] = []
    sample_ids: List[str] = []

    # Prepare ZIP file
    zip_filename = f"Student_QR_Codes_{batch_id}.zip"
    zip_filepath = settings.ZIP_STORAGE_DIR / zip_filename
    
    # Also maintain a standard 'Student_QR_Codes.zip' pointing to latest
    latest_zip_filepath = settings.ZIP_STORAGE_DIR / "Student_QR_Codes.zip"

    manifest_lines = [
        f"SMART QR STUDENT SLIP GENERATOR - BATCH MANIFEST",
        f"Batch ID: {batch_id}",
        f"Batch Label: {batch_label}",
        f"Total QR Slips: {count}",
        f"Generated At (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Verification URL Base: {effective_base_url}",
        f"-" * 70,
        f"{'Slip ID':<20} | {'Filename':<25} | {'Verification Status'}",
        f"-" * 70
    ]

    with zipfile.ZipFile(zip_filepath, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(count):
            slip_num = start_index + i
            formatted_num = f"{slip_num:0{pad_width}d}"
            slip_id = f"{prefix}{formatted_num}"

            # Generate cryptographically secure random token (256-bit entropy)
            raw_token = generate_slip_token()
            token_sha256 = hash_token(raw_token)
            signature = create_payload_signature(slip_id, raw_token)

            # Build verification URL
            verify_url = f"{effective_base_url}/verify?id={slip_id}&token={raw_token}&sig={signature}"

            # Create printable card image
            img = create_slip_qr_card(slip_id=slip_id, verification_url=verify_url)

            # Filename e.g. Slip_001.png
            filename = f"{slip_id}.png"
            filepath = batch_qr_dir / filename
            img.save(filepath, format="PNG", quality=95)

            # Add to ZIP archive
            zf.write(filepath, arcname=filename)
            generated_filenames.append(filename)

            # Store in DB
            slip_record = Slip(
                slip_id=slip_id,
                batch_id=batch_id,
                token_hash=token_sha256,
                status="ACTIVE",
                is_redeemed=False,
                notes=notes
            )
            db.add(slip_record)
            generated_slips.append(slip_record)

            if len(sample_ids) < 10:
                sample_ids.append(slip_id)

            manifest_lines.append(f"{slip_id:<20} | {filename:<25} | ACTIVE")

        # Add manifest file to the ZIP
        manifest_content = "\n".join(manifest_lines)
        zf.writestr("MANIFEST.txt", manifest_content)

    # Commit DB transaction
    db.commit()

    # Create Batch Record
    batch_record = BatchRecord(
        batch_id=batch_id,
        batch_name=batch_label,
        count=count,
        prefix=prefix,
        start_index=start_index,
        end_index=end_index,
        zip_filename=zip_filename
    )
    db.add(batch_record)
    db.commit()

    # Also copy/overwrite latest 'Student_QR_Codes.zip'
    try:
        import shutil
        shutil.copyfile(zip_filepath, latest_zip_filepath)
    except Exception:
        pass

    return {
        "success": True,
        "batch_id": batch_id,
        "batch_name": batch_label,
        "count": count,
        "start_index": start_index,
        "end_index": end_index,
        "zip_filename": zip_filename,
        "zip_filepath": str(zip_filepath),
        "latest_zip_filename": "Student_QR_Codes.zip",
        "sample_ids": sample_ids,
        "total_generated": len(generated_slips)
    }

def generate_single_slip_image(db: Session, slip_id: str, base_url: Optional[str] = None) -> Optional[Image.Image]:
    """Re-generate the printable QR card for an existing slip in the database."""
    slip = db.query(Slip).filter(Slip.slip_id == slip_id).first()
    if not slip:
        return None
    effective_base_url = (base_url or settings.VERIFY_BASE_URL).rstrip("/")
    # Even without the original raw token, the verify URL can be verified by Slip ID lookup
    verify_url = f"{effective_base_url}/verify?id={slip_id}"
    return create_slip_qr_card(slip_id=slip.slip_id, verification_url=verify_url)
