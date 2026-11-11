/**
 * Smart QR Student Slip Generator Page Logic
 */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("batchGeneratorForm");
    const countInput = document.getElementById("studentCountInput");
    const prefixInput = document.getElementById("prefixInput");
    const submitBtn = document.getElementById("generateBtn");
    const btnText = document.getElementById("generateBtnText");
    const spinner = document.getElementById("generateSpinner");
    const resultContainer = document.getElementById("generationResultCard");

    // Quick preset buttons (e.g. 30, 60, 100)
    const presetBtns = document.querySelectorAll(".preset-btn");
    presetBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const val = btn.getAttribute("data-count");
            if (countInput && val) {
                countInput.value = val;
            }
        });
    });

    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            const count = parseInt(countInput.value, 10);
            const prefix = prefixInput.value.trim() || "Slip_";
            const batchName = document.getElementById("batchNameInput") ? document.getElementById("batchNameInput").value.trim() : "";
            const notes = document.getElementById("notesInput") ? document.getElementById("notesInput").value.trim() : "";

            if (isNaN(count) || count < 1 || count > 1000) {
                alert("Please enter a valid student count between 1 and 1000.");
                return;
            }

            // Loading state
            submitBtn.disabled = true;
            if (btnText) btnText.innerText = `Generating ${count} QR Slips & ZIP...`;
            if (spinner) spinner.style.display = "inline-block";
            if (resultContainer) resultContainer.style.display = "none";

            try {
                const response = await fetch("/api/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        count: count,
                        prefix: prefix,
                        batch_name: batchName,
                        notes: notes
                    })
                });

                const data = await response.json();

                if (data.success) {
                    renderBatchResult(data);
                } else {
                    alert("Error: " + (data.message || "Failed to generate slips"));
                }
            } catch (err) {
                console.error("Batch generation error:", err);
                alert("Network error while generating QR codes. Please try again.");
            } finally {
                submitBtn.disabled = false;
                if (btnText) btnText.innerText = "Generate QR Codes";
                if (spinner) spinner.style.display = "none";
            }
        });
    }
});

function renderBatchResult(data) {
    const card = document.getElementById("generationResultCard");
    const batchIdSpan = document.getElementById("resBatchId");
    const countSpan = document.getElementById("resCount");
    const rangeSpan = document.getElementById("resRange");
    const downloadZipBtn = document.getElementById("resDownloadZipBtn");
    const samplesGrid = document.getElementById("resSamplesGrid");

    if (batchIdSpan) batchIdSpan.innerText = data.batch_id;
    if (countSpan) countSpan.innerText = data.count;
    if (rangeSpan) rangeSpan.innerText = `${data.start_index} to ${data.end_index}`;
    
    if (downloadZipBtn) {
        downloadZipBtn.href = data.zip_download_url;
        downloadZipBtn.innerHTML = `
            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
            </svg>
            Download ${data.zip_filename} (${data.count} Slips)
        `;
    }

    if (samplesGrid && data.sample_ids) {
        samplesGrid.innerHTML = data.sample_ids.map(id => `
            <div style="border: 1px solid var(--slate-200); border-radius: 8px; padding: 0.75rem; text-align: center; background: white;">
                <img src="/download/qr/${id}" alt="${id}" style="width: 100%; max-width: 140px; height: auto; border-radius: 4px; margin: 0 auto; display: block;" loading="lazy">
                <div style="font-size: 0.75rem; font-weight: 700; color: var(--slate-800); margin-top: 0.5rem;" class="font-mono">${id}</div>
                <a href="/download/qr/${id}" download="${id}.png" class="btn btn-secondary btn-sm" style="margin-top: 0.35rem; width: 100%;">PNG</a>
            </div>
        `).join("");
    }

    if (card) {
        card.style.display = "block";
        card.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}
