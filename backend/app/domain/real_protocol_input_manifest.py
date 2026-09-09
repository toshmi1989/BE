"""RealProtocolInputManifest — Phase 12C.

Describes a real or TECHNICAL_FIXTURE input package. Does not invent documents.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACKAGE_DIR = REPO_ROOT / "fixtures" / "packages" / "bosutinib-technical-v1"


@dataclass
class InputSourceEntry:
    source_id: str
    filename: str
    type: str  # design|test_product|reference|checklist|cv|previous_protocol|literature|other
    origin: str
    hash: str | None = None
    path: str | None = None
    ingestion_status: str = "PENDING"  # PENDING|OK|FAILED|SKIPPED
    extraction_status: str = "PENDING"
    completeness: str = "UNKNOWN"  # COMPLETE|PARTIAL|MISSING
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RealProtocolInputManifest:
    package_id: str
    classification: str  # REAL | TECHNICAL_FIXTURE
    package_root: str
    design_document: InputSourceEntry | None = None
    test_product_sources: list[InputSourceEntry] = field(default_factory=list)
    reference_product_sources: list[InputSourceEntry] = field(default_factory=list)
    checklist: InputSourceEntry | None = None
    cv_sources: list[InputSourceEntry] = field(default_factory=list)
    previous_protocol: InputSourceEntry | None = None
    additional_sources: list[InputSourceEntry] = field(default_factory=list)
    ingestion_version: str = "1"
    extraction_version: str = "1"
    test_run_id: str | None = None
    medical_validation: bool = False  # False for TECHNICAL_FIXTURE

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def all_entries(self) -> list[InputSourceEntry]:
        out: list[InputSourceEntry] = []
        if self.design_document:
            out.append(self.design_document)
        out.extend(self.test_product_sources)
        out.extend(self.reference_product_sources)
        if self.checklist:
            out.append(self.checklist)
        out.extend(self.cv_sources)
        if self.previous_protocol:
            out.append(self.previous_protocol)
        out.extend(self.additional_sources)
        return out


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry_from_dict(d: dict) -> InputSourceEntry:
    return InputSourceEntry(
        source_id=str(d["source_id"]),
        filename=str(d["filename"]),
        type=str(d["type"]),
        origin=str(d.get("origin") or "package"),
        hash=d.get("hash"),
        path=d.get("path"),
        ingestion_status=str(d.get("ingestion_status") or "PENDING"),
        extraction_status=str(d.get("extraction_status") or "PENDING"),
        completeness=str(d.get("completeness") or "UNKNOWN"),
        notes=d.get("notes"),
    )


def load_manifest(package_dir: Path | None = None) -> RealProtocolInputManifest:
    """Load manifest.json from package directory and refresh hashes for existing files."""
    root = Path(package_dir) if package_dir else DEFAULT_PACKAGE_DIR
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    classification = str(raw.get("classification") or "TECHNICAL_FIXTURE")
    medical = bool(raw.get("medical_validation", False))
    if classification == "TECHNICAL_FIXTURE":
        medical = False

    def resolve_entry(d: dict | None) -> InputSourceEntry | None:
        if not d:
            return None
        e = _entry_from_dict(d)
        rel = e.path or e.filename
        p = root / rel
        if p.is_file():
            e.hash = file_sha256(p)
            e.path = str(p.relative_to(root)).replace("\\", "/")
            if e.completeness == "UNKNOWN":
                e.completeness = "COMPLETE" if p.stat().st_size > 0 else "MISSING"
        else:
            e.completeness = "MISSING"
        return e

    return RealProtocolInputManifest(
        package_id=str(raw.get("package_id") or root.name),
        classification=classification,
        package_root=str(root),
        design_document=resolve_entry(raw.get("design_document")),
        test_product_sources=[e for e in (resolve_entry(x) for x in (raw.get("test_product_sources") or [])) if e],
        reference_product_sources=[
            e for e in (resolve_entry(x) for x in (raw.get("reference_product_sources") or [])) if e
        ],
        checklist=resolve_entry(raw.get("checklist")),
        cv_sources=[e for e in (resolve_entry(x) for x in (raw.get("cv_sources") or [])) if e],
        previous_protocol=resolve_entry(raw.get("previous_protocol")),
        additional_sources=[e for e in (resolve_entry(x) for x in (raw.get("additional_sources") or [])) if e],
        ingestion_version=str(raw.get("ingestion_version") or "1"),
        extraction_version=str(raw.get("extraction_version") or "1"),
        test_run_id=raw.get("test_run_id"),
        medical_validation=medical,
    )


def build_default_technical_manifest() -> RealProtocolInputManifest:
    """Convenience: load default TECHNICAL_FIXTURE package."""
    return load_manifest(DEFAULT_PACKAGE_DIR)
