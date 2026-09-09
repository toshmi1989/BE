/** Phase 27 — human-readable labels for writer UI (enums stay in API). */

const STATUS_RU: Record<string, string> = {
  READY: "Готово",
  APPROVED: "Утверждено",
  ACCEPTED: "Принято",
  BLOCKED: "Заблокировано",
  CRITICAL: "Критично",
  WARNING: "Предупреждение",
  PENDING: "Ожидает",
  OPEN: "Открыто",
  REVIEW_REQUIRED: "Требуется проверка",
  READY_WITH_WARNINGS: "Готово с предупреждениями",
  BLOCKED_PENDING_DECISIONS: "Заблокировано — ожидаются решения",
  CURRENT_STUDY_FACT: "Текущее значение",
  NO_CALCULATION: "Расчёт недоступен",
  NO_PLAN: "План недоступен",
  UPLOADED: "Загружено",
  PROCESSING: "Обработка",
  ERROR: "Ошибка",
  NONE: "Нет данных",
  DRAFT: "Черновик",
  COMPLETE: "Завершено",
  COMPLETED: "Завершено",
  REJECTED: "Отклонено",
  MODIFIED: "Изменено",
  RESOLVED_BY_EXPERT: "Решено экспертом",
  PRIMARY_BE: "PRIMARY BE",
  REQUIRES_EXPERT_DECISION: "Требуется решение эксперта",
  REQUIRES_EXPERT_SELECTION: "Требуется выбор эксперта",
  MISSING_VERIFIED_CVINTRA: "Нет подтверждённого CVintra",
  CONFLICTING_ENDPOINT_DEFINITIONS: "Конфликт определений endpoint",
  NOT_STARTED: "Не начато",
  IN_PROGRESS: "В работе",
  PRESENT: "Есть",
  MISSING: "Нет",
  OPTIONAL: "Опционально",
  CLASSIFIED: "Классифицировано",
  EXTRACTED: "Извлечено",
  PASS: "Пройдено",
  WARN: "С предупреждениями",
};

export function humanLabel(raw: unknown, fallback = "—"): string {
  if (raw == null || raw === "") return fallback;
  const s = String(raw);
  if (STATUS_RU[s]) return STATUS_RU[s];
  if (STATUS_RU[s.toUpperCase()]) return STATUS_RU[s.toUpperCase()];
  if (/^[A-Z0-9_]+$/.test(s) && s.includes("_")) {
    const mapped = STATUS_RU[s];
    if (mapped) return mapped;
    return s
      .split("_")
      .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
      .join(" ");
  }
  return s;
}

export function docStatusLabel(status: unknown): string {
  const s = String(status || "UPLOADED").toUpperCase();
  return STATUS_RU[s] || humanLabel(s);
}

export function stepStatusLabel(status: unknown): string {
  return humanLabel(status);
}

export const DEMO_STUDY_ID = "UPDCB-02-BE-2026";

export function isDemoStudy(studyId: string | null | undefined): boolean {
  return String(studyId || "") === DEMO_STUDY_ID || String(studyId || "").includes("UPDCB-02-BE-2026");
}

export const ANALYZE_STAGES = [
  "Uploading",
  "Ingesting",
  "Classifying",
  "Extracting",
  "Normalizing",
  "Validating",
  "Detecting conflicts",
  "Preparing review",
] as const;
