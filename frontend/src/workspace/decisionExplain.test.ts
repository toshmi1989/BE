import { describe, expect, it } from "vitest";
import {
  domainTitle,
  explainBlocker,
  explainDecisionBlockers,
  optionTitle,
  primaryNextAction,
} from "./decisionExplain";

describe("decisionExplain", () => {
  it("maps washout/sampling gaps to human next actions", () => {
    const w = explainBlocker({ blocking_reason_code: "MISSING_HALF_LIFE_FOR_WASHOUT" });
    expect(w.title).toMatch(/t½|полувывед/i);
    expect(w.next).toMatch(/Пробелы|источник/i);
    expect(w.nextTab).toBe("gaps");

    const s = explainBlocker("MISSING_TMAX_FOR_SAMPLING");
    expect(s.title).toMatch(/ожидаем|Tmax/i);
    expect(s.why).toMatch(/продолжаются|планов/i);
    expect(s.next).toMatch(/Пробелы|подтвержден/i);
    expect(s.nextTab).toBe("gaps");
  });

  it("explains decision blockers list", () => {
    const list = explainDecisionBlockers({
      status: "BLOCKED",
      blocking_reasons: [{ blocking_reason_code: "MISSING_HALF_LIFE_FOR_WASHOUT" }],
    });
    expect(list).toHaveLength(1);
    expect(primaryNextAction(list)).toMatch(/t½|Пробелы|источник/i);
  });

  it("humanizes domain and option", () => {
    expect(domainTitle("WASHOUT")).toMatch(/Washout/i);
    expect(optionTitle("FIXED_DURATION")).toMatch(/Фиксирован/i);
  });
});
