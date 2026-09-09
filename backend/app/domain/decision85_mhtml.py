"""MHTML / MIME .doc text extraction for Decision 85 web-archive.

Does not invent page numbers. Returns plain text only.
"""

from __future__ import annotations

import email
import re
from email import policy
from html.parser import HTMLParser
from pathlib import Path


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = False

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in ("script", "style"):
            self.skip = True
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in ("script", "style"):
            self.skip = False
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "td"):
            self.parts.append("\n")

    def handle_data(self, data):  # noqa: ANN001
        if not self.skip:
            self.parts.append(data)


def extract_mhtml_text(path: Path) -> str:
    raw = path.read_bytes()
    if not raw.startswith(b"MIME-Version"):
        raise ValueError("Not an MHTML/MIME web-archive")
    msg = email.message_from_bytes(raw, policy=policy.default)
    html: str | None = None
    for p in msg.walk():
        if p.get_content_type() not in ("text/html", "application/xhtml+xml"):
            continue
        payload = p.get_payload(decode=True) or b""
        for enc in ("utf-8", "utf-16", "utf-16-le", "cp1251", "latin-1"):
            try:
                cand = payload.decode(enc)
            except Exception:
                continue
            low = cand.lower()
            if "биоэквивалент" in low or "референт" in low or "решение совета" in low:
                html = cand
                break
            if html is None and "<" in cand and len(cand) > 1000:
                html = cand
        if html and ("биоэквивалент" in html.lower() or "референт" in html.lower()):
            break
    if not html:
        raise ValueError(f"No HTML body found in {path}")
    parser = _HTMLText()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[\t\xa0]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def flatten_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
