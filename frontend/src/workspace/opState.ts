/** Operation-local busy/error — unrelated nav stays usable. */

export type OpKey =
  | "upload"
  | "classify"
  | "workflow"
  | "decision"
  | "sampleSize"
  | "statistics"
  | "protocol"
  | "preflight"
  | "docx";

export type OpEntry = { busy: boolean; error: string | null };

export type OpState = Record<OpKey, OpEntry>;

export function initialOpState(): OpState {
  const keys: OpKey[] = [
    "upload",
    "classify",
    "workflow",
    "decision",
    "sampleSize",
    "statistics",
    "protocol",
    "preflight",
    "docx",
  ];
  const state = {} as OpState;
  for (const k of keys) {
    state[k] = { busy: false, error: null };
  }
  return state;
}

export function setOpBusy(prev: OpState, key: OpKey, busy: boolean): OpState {
  return { ...prev, [key]: { ...prev[key], busy, error: busy ? null : prev[key].error } };
}

export function setOpError(prev: OpState, key: OpKey, error: string | null): OpState {
  return { ...prev, [key]: { ...prev[key], busy: false, error } };
}

export function clearOpError(prev: OpState, key: OpKey): OpState {
  return { ...prev, [key]: { ...prev[key], error: null } };
}
