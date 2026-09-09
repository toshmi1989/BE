"""Evidence field definition registry — target entity/field mapping."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvidenceFieldDefinition:
    code: str
    expected_type: str  # string | number | range | boolean
    unit: str | None
    target_entity: str
    target_field: str
    evidence_type: str
    description: str


EVIDENCE_FIELD_DEFINITIONS: tuple[EvidenceFieldDefinition, ...] = (
    EvidenceFieldDefinition("reference_product", "string", None, "ReferenceProduct", "trade_name", "REFERENCE", "Reference trade name"),
    EvidenceFieldDefinition("registration_status", "string", None, "ReferenceProduct", "registration_status", "REGISTRATION", "Registration status"),
    EvidenceFieldDefinition("dosage", "string", None, "Product", "dosage", "REFERENCE", "Strength / dosage"),
    EvidenceFieldDefinition("dosage_form", "string", None, "Product", "dosage_form", "REFERENCE", "Dosage form"),
    EvidenceFieldDefinition("food_condition", "string", None, "FoodCondition", "condition", "FOOD", "Fed / fasting"),
    EvidenceFieldDefinition("tmax", "range", "h", "Analyte", "tmax", "PK", "Tmax range"),
    EvidenceFieldDefinition("half_life", "range", "h", "Analyte", "half_life", "PK", "Half-life range"),
    EvidenceFieldDefinition("analyte", "string", None, "Analyte", "name", "ANALYTE", "Analyte name"),
    EvidenceFieldDefinition("design", "string", None, "Design", "type", "DESIGN", "Study design"),
    EvidenceFieldDefinition("cv_cmax", "number", "percent", "CVStudy", "cv_value", "CV", "Within-subject CV for Cmax"),
    EvidenceFieldDefinition("cv_auc", "number", "percent", "CVStudy", "cv_value", "CV", "Within-subject CV for AUC"),
    EvidenceFieldDefinition("study_n", "number", None, "CVStudy", "n_total", "CV", "Total subjects in source study"),
    EvidenceFieldDefinition("study_n_be_analysis", "number", None, "CVStudy", "n_be_analysis", "CV", "Subjects in BE analysis"),
    EvidenceFieldDefinition("safety_statement", "string", None, "Study", "notes", "SAFETY", "Safety narrative excerpt"),
)

EVIDENCE_FIELDS_VERSION = "EVIDENCE.FIELDS.v1"


def field_by_code(code: str) -> EvidenceFieldDefinition | None:
    for d in EVIDENCE_FIELD_DEFINITIONS:
        if d.code == code:
            return d
    return None


def fields_as_list() -> list[dict]:
    return [
        {**asdict(d), "version": EVIDENCE_FIELDS_VERSION}
        for d in EVIDENCE_FIELD_DEFINITIONS
    ]
