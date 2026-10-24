"""Cache pinned primary sources for the 2026-10-24 idea screen; no inference."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent / "sources"
SOURCES = [
    ("das_self_propagation_2610_04083v1", "https://arxiv.org/pdf/2610.04083v1"),
    ("yang_sok_2609_00595v1", "https://arxiv.org/pdf/2609.00595v1"),
    ("idowu_mapping_2601_00360v3", "https://arxiv.org/pdf/2601.00360v3"),
    ("pandey_integrity_2609_34245v1", "https://arxiv.org/pdf/2609.34245v1"),
    ("gao_interchangeability_2609_05279v1", "https://arxiv.org/pdf/2609.05279v1"),
    ("ma_flp_2605_01758v3", "https://arxiv.org/pdf/2605.01758v3"),
    ("alnuhait_covert_2609_39050v1", "https://arxiv.org/pdf/2609.39050v1"),
    ("hu_truths_acl2026_270", "https://aclanthology.org/2026.acl-long.270.pdf"),
    ("li_safeflow_2506_07564v3", "https://arxiv.org/pdf/2506.07564v3"),
    ("li_mesa_2606_30602v1", "https://arxiv.org/pdf/2606.30602v1"),
]


def fetch(source):
    key, url = source
    pdf = ROOT / f"{key}.pdf"
    result = {"id": key, "url": url}
    try:
        if not pdf.exists():
            subprocess.run(
                ["curl", "--fail", "--location", "--silent", "--show-error",
                 "--max-time", "35", "--output", str(pdf), url],
                check=True, capture_output=True, text=True,
            )
        raw = pdf.read_bytes()
        reader = PdfReader(pdf)
        txt = pdf.with_suffix(".txt")
        txt.write_text("\n\n".join(
            f"=== PDF PAGE {i + 1} ===\n{page.extract_text()}"
            for i, page in enumerate(reader.pages)
        ))
        result.update(status="ok", pdf=str(pdf.relative_to(ROOT.parent)),
                      text=str(txt.relative_to(ROOT.parent)), pages=len(reader.pages),
                      sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    except Exception as error:
        result.update(status="failed", error=str(error))
        if pdf.exists() and not pdf.read_bytes().startswith(b"%PDF"):
            pdf.unlink()
    return result


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, SOURCES))
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Primary-source novelty screen; authors' findings not replicated",
        "sources": results,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps([{k: r[k] for k in ("id", "status", "pages", "error") if k in r}
                      for r in results], indent=2))
