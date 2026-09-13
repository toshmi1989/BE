"""Reading values out of PK tables — Phase 29.2.

Variability is tabulated far more often than it is written in a sentence: the
row names the PK parameter, the column names the statistic. Prose extraction
reads sentences, so those numbers stayed invisible and CVintra had to be typed
in by hand even when the source stated it.

This module rebuilds table rows out of extracted text — PDF lines, DOCX pipes,
HTML cells — and reports a cell only when both its row and its column say what
the number is. A cell without a number, a table without a variability column,
and a table that never says within- or between-subject produce nothing or
UNKNOWN: the qualifier is never guessed, and a row whose cell count does not
match the header is left unread rather than attributed to the wrong column.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.domain.research_extract import variability_type
from app.domain.research_sanitize import strip_html

# Cell and row boundaries must survive tag stripping, which drops control
# characters and collapses whitespace. Private-use code points do not occur in
# source documents, so they can carry the grid through it.
CELL_MARK = "\ue000"
ROW_MARK = "\ue001"

_CELL_END_RE = re.compile(r"</\s*t[dh]\s*>", re.I)
_ROW_END_RE = re.compile(
    r"</\s*tr\s*>|</\s*table\s*>|<\s*br\s*/?>|</\s*p\s*>|</\s*li\s*>|</\s*h[1-6]\s*>",
    re.I,
)


def html_text_with_tables(raw: str | None) -> str:
    """Strip tags but keep the grid: cells joined by ' | ', rows on own lines."""
    if not raw:
        return ""
    marked = _CELL_END_RE.sub(CELL_MARK, raw)
    marked = _ROW_END_RE.sub(ROW_MARK, marked)
    flat = strip_html(marked)
    lines: list[str] = []
    for chunk in flat.split(ROW_MARK):
        cells = [c.strip() for c in chunk.split(CELL_MARK)]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


@dataclass
class TableBlock:
    """Consecutive rows read as one table, with the line that titles it."""

    rows: list[list[str]] = field(default_factory=list)
    caption: str = ""

    def text(self) -> str:
        return " ".join(" ".join(r) for r in self.rows)


@dataclass
class TableFinding:
    """One variability cell, carried with the row and column that explain it."""

    pk_parameter: str
    variability_type: str
    value: Any = None
    range_low: Any = None
    range_high: Any = None
    unit: str = "%"
    row_label: str = ""
    column_label: str = ""
    caption: str = ""
    excerpt: str = ""

    def as_metadata(self) -> dict[str, Any]:
        """Metadata the deterministic extractor reads instead of re-parsing."""
        return {
            "parameter": "CVintra",
            "CV_value": self.value,
            "CV_range_low": self.range_low,
            "CV_range_high": self.range_high,
            "CV_unit": self.unit,
            "PK_parameter": self.pk_parameter,
            "variability_type": self.variability_type,
            "read_mode": "TABLE",
        }


_PIPE_SPLIT = re.compile(r"\s*\|\s*")
_GAP_SPLIT = re.compile(r"\s{2,}|\t+")


def _row_cells(line: str) -> list[str]:
    """Cells of one line. Pipes when present, otherwise column gaps."""
    parts = _PIPE_SPLIT.split(line) if "|" in line else _GAP_SPLIT.split(line.strip())
    return [p.strip() for p in parts if p and p.strip()]


def split_table_rows(text: str, *, min_cells: int = 2, min_rows: int = 2) -> list[TableBlock]:
    """Group the lines that look like table rows, keeping the caption above them."""
    blocks: list[TableBlock] = []
    current: list[list[str]] = []
    caption = ""
    last_prose = ""

    def close() -> None:
        nonlocal current
        if len(current) >= min_rows:
            blocks.append(TableBlock(rows=current, caption=caption))
        current = []

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        cells = _row_cells(line) if line else []
        if len(cells) >= min_cells:
            if not current:
                caption = last_prose
            current.append(cells)
            continue
        close()
        if line:
            last_prose = line
    close()
    return blocks


_CV_LABEL_RE = re.compile(
    r"\bCV\b|CV\s*%|%\s*CV|coefficient\s+of\s+variation|вариабельн\w*|коэффициент\s+вариации",
    re.I,
)
_AVERAGE_RE = re.compile(r"mean|median|geometric|средн\w*|медиан\w*", re.I)
_PAREN_CV_RE = re.compile(r"\(\s*[^)]*CV[^)]*\)", re.I)

_NUM = r"\d{1,3}(?:[.,]\d+)?"
_RANGE_RE = re.compile(rf"({_NUM})\s*%?\s*(?:[-–—]|to|до)\s*({_NUM})")
_POINT_RE = re.compile(rf"({_NUM})")
_PAREN_NUM_RE = re.compile(rf"\(\s*({_NUM})\s*%?\s*\)")
_NOT_STATED_RE = re.compile(
    r"^(?:n\.?\s*[adr]\.?|nr|na|nd|not\s+reported|not\s+available|нет\s+данных|[-–—]+|\*+)$",
    re.I,
)
# A coefficient of variation above this is not a CV but some other figure
_MAX_CV_PERCENT = 200.0

_PK_LABEL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("AUC0-t", r"AUC\s*[_(]?\s*0\s*[-–—]?\s*(?:t\b|last|tlast)"),
    ("AUC0-inf", r"AUC\s*[_(]?\s*0\s*[-–—]?\s*(?:inf|∞)"),
    ("AUC", r"\bAUC\b"),
    ("Cmax", r"\bC\s*[-_]?\s*max\b|\bCmax\b"),
    ("Tmax", r"\bT\s*[-_]?\s*max\b|\bTmax\b"),
    ("t_half", r"t\s*1\s*/\s*2|t½|half[-\s]?li(?:fe|ves)|период\s+полувыведения"),
)


def _pk_parameter(label: str) -> str | None:
    for name, pattern in _PK_LABEL_PATTERNS:
        if re.search(pattern, label or "", re.I):
            return name
    return None


def _as_number(raw: str) -> float:
    return float(raw.replace(",", "."))


def _plausible(value: float) -> bool:
    return 0.0 < value <= _MAX_CV_PERCENT


def _cell_number(cell: str, *, parenthetical: bool) -> dict[str, Any] | None:
    """Read the number a cell states. An empty or 'not reported' cell states none."""
    raw = (cell or "").strip()
    if not raw or _NOT_STATED_RE.match(raw):
        return None
    if parenthetical:
        # "Mean (CV%)" columns hold the variability inside the brackets
        m = _PAREN_NUM_RE.search(raw)
        if not m:
            return None
        value = _as_number(m.group(1))
        return {"value": value} if _plausible(value) else None

    rng = _RANGE_RE.search(raw)
    if rng:
        low, high = _as_number(rng.group(1)), _as_number(rng.group(2))
        if low > high or not (_plausible(low) and _plausible(high)):
            return None
        return {"value": None, "range_low": low, "range_high": high}

    point = _POINT_RE.search(raw)
    if not point:
        return None
    value = _as_number(point.group(1))
    return {"value": value} if _plausible(value) else None


def _is_cv_column(label: str) -> bool:
    return bool(_CV_LABEL_RE.search(label or ""))


def _parenthetical_column(label: str) -> bool:
    """'Geometric Mean (CV%)' states the mean first and the CV in brackets."""
    return bool(_AVERAGE_RE.search(label or "")) and bool(_PAREN_CV_RE.search(label or ""))


def _qualifier(column_label: str, block: TableBlock) -> str:
    """Within- or between-subject, read from the most specific wording available."""
    for probe in (column_label, block.caption, block.text()):
        found = variability_type(probe or "")
        if found != "UNKNOWN":
            return found
    return "UNKNOWN"


def _excerpt(block: TableBlock, row: list[str], column_label: str, cell: str) -> str:
    """What the expert has to check: the cell, its labels, and the raw row."""
    head = "Таблица"
    if block.caption:
        head += f" «{block.caption[:70]}»"
    return (
        f"{head} · строка «{(row[0] if row else '')[:50]}» · "
        f"столбец «{column_label[:50]}» → {cell.strip()[:30]}; "
        f"строка целиком: {' | '.join(row)[:120]}"
    )


def _finding(
    block: TableBlock,
    row: list[str],
    column_label: str,
    cell: str,
    pk_parameter: str,
    number: dict[str, Any],
) -> TableFinding:
    return TableFinding(
        pk_parameter=pk_parameter,
        variability_type=_qualifier(column_label, block),
        value=number.get("value"),
        range_low=number.get("range_low"),
        range_high=number.get("range_high"),
        row_label=(row[0] if row else "")[:120],
        column_label=column_label[:120],
        caption=block.caption[:200],
        excerpt=_excerpt(block, row, column_label, cell),
    )


def _column_findings(block: TableBlock) -> list[TableFinding]:
    """Ordinary layout: PK parameter per row, variability in its own column."""
    out: list[TableFinding] = []
    for header_index, header in enumerate(block.rows):
        cv_columns = [i for i, cell in enumerate(header) if _is_cv_column(cell)]
        if not cv_columns:
            continue
        for row in block.rows[header_index + 1 :]:
            pk = _pk_parameter(row[0]) if row else None
            if not pk:
                continue
            # Dropped empty cells would shift the columns, so an unmatched row
            # is left unread instead of being attributed to a guessed column.
            offset = len(row) - len(header)
            if offset not in (0, 1):
                continue
            for column in cv_columns:
                index = column + offset
                if index >= len(row):
                    continue
                label = header[column]
                number = _cell_number(row[index], parenthetical=_parenthetical_column(label))
                if number is None:
                    continue
                out.append(_finding(block, row, label, row[index], pk, number))
        break
    return out


def _transposed_findings(block: TableBlock) -> list[TableFinding]:
    """Transposed layout: PK parameters in the header, variability in a row."""
    if not block.rows:
        return []
    header = block.rows[0]
    out: list[TableFinding] = []
    for row in block.rows[1:]:
        if not row or not _is_cv_column(row[0]) or len(row) != len(header):
            continue
        for index in range(1, len(row)):
            pk = _pk_parameter(header[index])
            if not pk:
                continue
            number = _cell_number(row[index], parenthetical=False)
            if number is None:
                continue
            out.append(_finding(block, row, row[0], row[index], pk, number))
    return out


def cv_table_findings(text: str, *, limit: int = 12) -> list[TableFinding]:
    """Variability values stated in the tables of a document, as stated."""
    out: list[TableFinding] = []
    seen: set[tuple[str, Any, Any, str]] = set()
    for block in split_table_rows(text):
        for finding in _column_findings(block) + _transposed_findings(block):
            key = (
                finding.pk_parameter,
                finding.value,
                (finding.range_low, finding.range_high),
                finding.variability_type,
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(finding)
            if len(out) >= limit:
                return out
    return out
