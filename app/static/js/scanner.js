/**
 * Smart QR Student Slip Scanner & Verifier
 * Powered by html5-qrcode with camera and image upload support.
 */

let html5QrCode = null;
let isScanning = false;
let currentCameraId = null;
let camerasList = [];
let audioCtx = null;

// Initialize Web Audio API for acoustic verification feedback
function playFeedbackSound(type) {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const now = audioCtx.currentTime;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === 'GENUINE') {
            // Pleasant success chime (C6 -> G6)
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1046.50, now);
            osc.frequency.exponentialRampToValueAtTime(1567.98, now + 0.12);
            gain.gain.setValueAtTime(0.2, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
            osc.start(now);
            osc.stop(now + 0.35);
        } else if (type === 'ALREADY_USED') {
            // Warning tone
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.setValueAtTime(350, now + 0.15);
            gain.gain.setValueAtTime(0.25, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
            osc.start(now);
            osc.stop(now + 0.4);
        } else {
            // Error / Invalid buzz
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(180, now);
            osc.frequency.setValueAtTime(130, now + 0.15);
            gain.gain.setValueAtTime(0.25, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
            osc.start(now);
            osc.stop(now + 0.45);
        }
    } catch (e) {
        console.warn("Audio feedback not supported or blocked by autoplay policy.", e);
    }
}

// Mobile haptic vibration feedback
function triggerVibration(pattern) {
    if (navigator.vibrate) {
        navigator.vibrate(pattern);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const switchBtn = document.getElementById("switchCameraBtn");
    const fileInput = document.getElementById("qrFileInput");
    const dropZone = document.getElementById("qrDropZone");
    const manualForm = document.getElementById("manualLookupForm");

    // Camera Start
    if (startBtn) {
        startBtn.addEventListener("click", startCamera);
    }

    // Camera Stop
    if (stopBtn) {
        stopBtn.addEventListener("click", stopCamera);
    }

    // Switch Camera (Front/Back)
    if (switchBtn) {
        switchBtn.addEventListener("click", switchCamera);
    }

    // File Input Upload
    if (fileInput) {
        fileInput.addEventListener("change", handleFileScan);
    }

    // Drag and Drop Zone
    if (dropZone) {
        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("border-primary");
        });
        dropZone.addEventListener("dragleave", () => {
            dropZone.classList.remove("border-primary");
        });
        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropZone.classList.remove("border-primary");
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                scanImageFile(e.dataTransfer.files[0]);
            }
        });
    }

    // Manual Form Lookup
    if (manualForm) {
        manualForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const input = document.getElementById("manualPayloadInput");
            if (input && input.value.trim()) {
                verifyPayload(input.value.trim());
            }
        });
    }

    // Auto-discover cameras
    if (window.Html5Qrcode) {
        Html5Qrcode.getCameras().then(devices => {
            if (devices && devices.length) {
                camerasList = devices;
                if (switchBtn && devices.length > 1) {
                    switchBtn.style.display = "inline-flex";
                }
            }
        }).catch(err => {
            console.log("No initial cameras found or permission not yet requested.");
        });
    }
});

async function startCamera() {
    if (!window.Html5Qrcode) {
        alert("QR scanning library failed to load. Please check your internet connection or reload.");
        return;
    }

    if (!html5QrCode) {
        html5QrCode = new Html5Qrcode("reader");
    }

    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const laser = document.getElementById("scannerLaser");

    const qrConfig = {
        fps: 15,
        qrbox: { width: 260, height: 260 },
        aspectRatio: 1.0,
    };

    try {
        // Prefer rear camera on mobile devices
        const cameraConfig = { facingMode: "environment" };

        await html5QrCode.start(
            cameraConfig,
            qrConfig,
            onQrCodeSuccess,
            (errorMessage) => {
                // Ignore per-frame decode errors
            }
        );

        isScanning = true;
        if (startBtn) startBtn.style.display = "none";
        if (stopBtn) stopBtn.style.display = "inline-flex";
        if (laser) laser.style.display = "block";
    } catch (err) {
        console.error("Camera access error:", err);
        alert("Could not access camera. Please check camera permissions in your browser or try the file upload option.");
    }
}

async function stopCamera() {
    if (html5QrCode && isScanning) {
        try {
            await html5QrCode.stop();
            isScanning = false;
        } catch (err) {
            console.error("Error stopping camera:", err);
        }
    }
    const startBtn = document.getElementById("startCameraBtn");
    const stopBtn = document.getElementById("stopCameraBtn");
    const laser = document.getElementById("scannerLaser");

    if (startBtn) startBtn.style.display = "inline-flex";
    if (stopBtn) stopBtn.style.display = "none";
    if (laser) laser.style.display = "none";
}

async function switchCamera() {
    if (!html5QrCode || !isScanning) return;
    await stopCamera();
    // Toggle camera
    startCamera();
}

// Handler when QR code is detected by camera
function onQrCodeSuccess(decodedText, decodedResult) {
    if (!isScanning) return;
    
    // Pause scanner to prevent duplicate triggers
    if (html5QrCode) {
        html5QrCode.pause();
    }

    verifyPayload(decodedText);
}

// File upload handler
function handleFileScan(e) {
    if (e.target.files && e.target.files.length > 0) {
        scanImageFile(e.target.files[0]);
    }
}

async function scanImageFile(file) {
    if (!file) return;
    const scanner = new Html5Qrcode("reader-hidden-file");
    try {
        const decodedText = await scanner.scanFile(file, true);
        verifyPayload(decodedText);
    } catch (err) {
        alert("No readable QR code found in the uploaded image. Please ensure the QR code is clearly visible and in focus.");
    } finally {
        scanner.clear();
    }
}

// Send payload to backend /api/verify
async function verifyPayload(payloadText) {
    const modal = document.getElementById("resultModal");
    const modalContent = document.getElementById("modalResultContainer");

    try {
        const resp = await fetch("/api/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ payload: payloadText })
        });

        const data = await resp.json();
        renderResultCard(data);
    } catch (err) {
        console.error("Verification network error:", err);
        renderResultCard({
            status: "INVALID",
            status_code: "invalid",
            title: "VERIFICATION ERROR",
            message: "Unable to reach verification server. Please check your connection."
        });
    }
}

// Render the 4 official states in the modal
function renderResultCard(data) {
    const modal = document.getElementById("resultModal");
    const container = document.getElementById("modalResultContainer");
    if (!modal || !container) return;

    // Trigger audio & haptic feedback
    playFeedbackSound(data.status);
    if (data.status === "GENUINE") {
        triggerVibration([100, 50, 100]);
    } else {
        triggerVibration([250]);
    }

    let statusClass = "result-invalid";
    let iconSvg = "";
    
    if (data.status === "GENUINE") {
        statusClass = "result-genuine";
        iconSvg = `
            <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path>
            </svg>`;
    } else if (data.status === "ALREADY_USED") {
        statusClass = "result-already-used";
        iconSvg = `
            <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
            </svg>`;
    } else if (data.status === "REVOKED") {
        statusClass = "result-revoked";
        iconSvg = `
            <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path>
            </svg>`;
    } else {
        // INVALID
        statusClass = "result-invalid";
        iconSvg = `
            <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"></path>
            </svg>`;
    }

    let metaHtml = "";
    if (data.slip_id) {
        metaHtml += `
            <div class="result-meta-box">
                <div class="meta-row">
                    <span class="meta-label">Unique Slip ID</span>
                    <span class="meta-value font-mono text-base">${data.slip_id}</span>
                </div>
                ${data.created_at ? `
                <div class="meta-row">
                    <span class="meta-label">Issue Date</span>
                    <span class="meta-value">${data.created_at}</span>
                </div>` : ''}
                ${data.batch_id ? `
                <div class="meta-row">
                    <span class="meta-label">Batch ID</span>
                    <span class="meta-value text-xs">${data.batch_id}</span>
                </div>` : ''}
                <div class="meta-row">
                    <span class="meta-label">Usage Status</span>
                    <span class="meta-value">
                        ${data.is_redeemed ? '<span class="badge badge-redeemed">Redeemed</span>' : '<span class="badge badge-genuine">Active / Unused</span>'}
                    </span>
                </div>
                ${data.redeemed_at ? `
                <div class="meta-row">
                    <span class="meta-label">Redeemed At</span>
                    <span class="meta-value text-amber-700">${data.redeemed_at}</span>
                </div>` : ''}
                ${data.revoked_at ? `
                <div class="meta-row">
                    <span class="meta-label">Revocation Date</span>
                    <span class="meta-value text-red-600">${data.revoked_at}</span>
                </div>` : ''}
            </div>
        `;
    }

    // Action buttons
    let actionButtons = `
        <div style="display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap;">
            ${data.can_redeem ? `
            <button id="modalRedeemBtn" onclick="redeemCurrentSlip('${data.slip_id}')" class="btn btn-warning">
                <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                Mark as Redeemed
            </button>` : ''}
            <button onclick="closeResultModal()" class="btn btn-primary">
                <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                Scan Next Slip
            </button>
        </div>
    `;

    container.innerHTML = `
        <div class="result-card ${statusClass}">
            <div class="result-icon-circle">
                ${iconSvg}
            </div>
            <h2 class="result-title">${data.title}</h2>
            <p class="result-message">${data.message}</p>
            ${metaHtml}
            ${actionButtons}
        </div>
    `;

    modal.style.display = "flex";
}

// Mark slip as redeemed action from scanner modal
async function redeemCurrentSlip(slipId) {
    const btn = document.getElementById("modalRedeemBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerText = "Marking Redeemed...";
    }

    try {
        const resp = await fetch("/api/redeem", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slip_id: slipId })
        });
        const data = await resp.json();
        if (data.success) {
            // Re-verify to display updated ALREADY REDEEMED state
            verifyPayload(slipId);
        } else {
            alert(data.message || "Failed to redeem slip.");
            if (btn) {
                btn.disabled = false;
                btn.innerText = "Mark as Redeemed";
            }
        }
    } catch (e) {
        alert("Error marking slip as redeemed.");
        if (btn) btn.disabled = false;
    }
}

function closeResultModal() {
    const modal = document.getElementById("resultModal");
    if (modal) {
        modal.style.display = "none";
    }
    // Resume camera if scanner is active
    if (html5QrCode && isScanning) {
        try {
            html5QrCode.resume();
        } catch (e) {
            console.log("Error resuming scanner:", e);
        }
    }
}
