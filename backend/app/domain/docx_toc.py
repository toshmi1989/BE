"""Phase 30.3 — TOC field refresh after DOCX render.

Uses LibreOffice when available. Otherwise clears stale numeric page
references in TOC paragraphs so template page numbers cannot survive.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from docx import Document

_TOC_PAGE_TAIL = re.compile(r"(\t|\s{2,})\d+\s*$")


def _find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


def refresh_toc_fields(path: Path) -> dict[str, Any]:
    """Attempt TOC refresh. Always returns a status dict."""
    soffice = _find_soffice()
    if soffice:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                # Open/re-save via LO can update fields when macro-enabled; best-effort.
                cmd = [
                    soffice,
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    tmp,
                    str(path),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                out = Path(tmp) / path.name
                if proc.returncode == 0 and out.exists():
                    path.write_bytes(out.read_bytes())
                    return {
                        "toc_refreshed": True,
                        "method": "libreoffice_convert",
                        "detail": (proc.stdout or "")[:200],
                    }
                return {
                    "toc_refreshed": False,
                    "method": "libreoffice_failed",
                    "detail": (proc.stderr or proc.stdout or "")[:300],
                }
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
            return {"toc_refreshed": False, "method": "libreoffice_error", "detail": str(exc)}

    # Fallback: strip stale page numbers from TOC-styled paragraphs
    cleared = clear_stale_toc_page_numbers(path)
    return {
        "toc_refreshed": True,
        "method": "clear_stale_page_numbers",
        "detail": cleared,
    }


def clear_stale_toc_page_numbers(path: Path) -> dict[str, Any]:
    doc = Document(str(path))
    cleared = 0
    toc_paras = 0
    for p in doc.paragraphs:
        style = (p.style.name if p.style else "") or ""
        text = p.text or ""
        is_toc = style.lower().startswith("toc") or "оглавление" in text.lower()[:40]
        if not is_toc and not (style.startswith("TOC") or "toc " in style.lower()):
            # also treat dense dotted leaders as TOC lines
            if "...." not in text and "…" not in text and "\t" not in text:
                continue
        toc_paras += 1
        new_text = _TOC_PAGE_TAIL.sub("", text).rstrip()
        # also strip trailing page number after dots
        new_text = re.sub(r"(\.{2,}|\u2026)\s*\d+\s*$", r"\1", new_text)
        if new_text != text:
            for r in list(p.runs):
                r._element.getparent().remove(r._element)
            p.add_run(new_text)
            cleared += 1
    doc.save(str(path))
    return {"cleared": cleared, "toc_paras": toc_paras, "no_toc": toc_paras == 0}
