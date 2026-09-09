/** Human explanations for Decision Center blockers and next actions. */

export type BlockerExplain = {
  code: string;
  title: string;
  why: string;
  next: string;
  nextTab?: "data" | "evidence" | "documents" | "decisions";
};

const GAP_EXPLAIN: Record<string, Omit<BlockerExplain, "code">> = {
  MISSING_HALF_LIFE_FOR_WASHOUT: {
    title: "Нет периода полувыведения (t½)",
    why: "Без t½ нельзя безопасно утвердить washout — это медицинский вход, а не UI-ограничение.",
    next: "Найдите t½ в SmPC / источниках (вкладка Данные или Evidence) или запросите evidence.",
    nextTab: "evidence",
  },
  MISSING_TMAX_FOR_SAMPLING: {
    title: "Нет Tmax",
    why: "Профиль sampling зависит от Tmax; без него утверждение sampling заблокировано.",
    next: "Добавьте / подтвердите Tmax из PK-источников или запросите evidence.",
    nextTab: "evidence",
  },
  MISSING_CVINTRA: {
    title: "Нет CVintra",
    why: "Внутрииндивидуальная вариабельность нужна для sample size / статистики.",
    next: "Укажите verified CVintra из литературы или Research Center.",
    nextTab: "evidence",
  },
  MISSING_ANALYTE: {
    title: "Не указан analyte",
    why: "Решение по PK/analyte требует идентифицированного вещества.",
    next: "Проверьте извлечённые факты и источники по analyte.",
    nextTab: "data",
  },
  MISSING_MEAL_COMPOSITION: {
    title: "Нет состава приёма пищи",
    why: "Для food-решения желателен meal composition (не всегда critical).",
    next: "При необходимости уточните meal composition в источниках.",
    nextTab: "data",
  },
};

const DOMAIN_RU: Record<string, string> = {
  DESIGN: "Дизайн исследования",
  FOOD: "Пищевой режим (food)",
  WASHOUT: "Washout (период отмывки)",
  SAMPLING: "Sampling (профиль забора)",
  ANALYTE_PK: "Analyte / PK",
  STATISTICS: "Статистика",
};

const OPTION_RU: Record<string, string> = {
  STANDARD_2X2_CROSSOVER: "Стандартный 2×2 crossover",
  REPLICATE_DESIGN: "Replicate design",
  PARALLEL: "Параллельный дизайн",
  FIXED_DURATION: "Фиксированная длительность",
  STANDARD_PROFILE: "Стандартный профиль sampling",
  FED: "Fed (после еды)",
  FASTED: "Fasted (натощак)",
};

export function domainTitle(domain: unknown): string {
  const d = String(domain || "").toUpperCase();
  return DOMAIN_RU[d] || String(domain || "Решение");
}

export function optionTitle(raw: unknown): string {
  if (raw == null || raw === "") return "—";
  const s = String(raw);
  return OPTION_RU[s] || OPTION_RU[s.toUpperCase()] || s;
}

function blockerCodeOf(raw: unknown): string {
  if (typeof raw === "string") return raw;
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    return String(o.blocking_reason_code || o.code || o.reason || "").trim();
  }
  return "";
}

function blockerMessageOf(raw: unknown): string {
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    return String(o.message || "").trim();
  }
  return "";
}

export function explainBlocker(raw: unknown): BlockerExplain {
  const code = blockerCodeOf(raw);
  const known = GAP_EXPLAIN[code];
  if (known) return { code, ...known };

  if (code.startsWith("CONFLICT_")) {
    const field = code.replace(/^CONFLICT_/, "").toLowerCase().replace(/_/g, ".");
    return {
      code,
      title: `Открытый конфликт: ${field}`,
      why: "Пока конфликт не закрыт экспертом, связанные решения нельзя утвердить.",
      next: "Сравните источники A/B и утвердите выбранное значение по конфликту.",
      nextTab: "decisions",
    };
  }

  if (code.startsWith("UNRELATED_CONFLICT_")) {
    return {
      code,
      title: "Есть несвязанный конфликт",
      why: "Конфликт в другом поле не блокирует это решение напрямую (информативно).",
      next: "Можно продолжить с этим решением; конфликт закройте отдельно.",
      nextTab: "decisions",
    };
  }

  const msg = blockerMessageOf(raw);
  return {
    code: code || "BLOCKER",
    title: msg || (code ? humanizeCode(code) : "Есть ограничение"),
    why: msg || "Система требует закрыть зависимость перед утверждением.",
    next: "Откройте детали решения: Blockers / Evidence, затем Request evidence или внесите данные.",
    nextTab: "evidence",
  };
}

function humanizeCode(code: string): string {
  return code
    .split("_")
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(" ");
}

export function explainDecisionBlockers(decision: Record<string, unknown>): BlockerExplain[] {
  const reasons = Array.isArray(decision.blocking_reasons) ? decision.blocking_reasons : [];
  const conflicts = Array.isArray(decision.blocking_conflicts) ? decision.blocking_conflicts : [];
  const out: BlockerExplain[] = [];
  const seen = new Set<string>();

  for (const r of reasons) {
    const e = explainBlocker(r);
    if (seen.has(e.code)) continue;
    seen.add(e.code);
    out.push(e);
  }
  for (const fp of conflicts) {
    const code = `CONFLICT_${String(fp).replace(/\./g, "_").toUpperCase()}`;
    if (seen.has(code)) continue;
    seen.add(code);
    out.push(explainBlocker({ blocking_reason_code: code, field_path: fp }));
  }

  if (!out.length && String(decision.status || "").toUpperCase() === "BLOCKED") {
    out.push({
      code: "BLOCKED",
      title: "Решение заблокировано",
      why: "Не хватает обязательных входов или есть незакрытые зависимости.",
      next: "Откройте карточку → Blockers. Обычно нужны t½, Tmax или закрытие конфликта.",
      nextTab: "evidence",
    });
  }
  return out;
}

export function primaryNextAction(explains: BlockerExplain[]): string {
  if (!explains.length) return "Можно утвердить рекомендацию или изменить значение.";
  return explains[0]!.next;
}

export const AI_ROLE_COPY = {
  title: "Роль ИИ в Writer",
  bullets: [
    "ИИ помогает извлекать факты из документов и формулировать рекомендации.",
    "ИИ не утверждает решения, не закрывает конфликты и не финализирует протокол.",
    "Утверждение (Approve) — только эксперт / writer с правом approve_decisions.",
    "При выключенном AI (AI_ENABLED=false) workflow всё равно работает: правила и расчёты детерминированы.",
  ],
} as const;
