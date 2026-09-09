import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("client auth token + ApiError", () => {
  beforeEach(() => {
    vi.resetModules();
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("injects Bearer token and persists to sessionStorage", async () => {
    const { setAuthToken, getAuthToken, resolveApiBase } = await import("./client");
    setAuthToken("tok-abc");
    expect(getAuthToken()).toBe("tok-abc");
    expect(sessionStorage.getItem("be_auth_token")).toBe("tok-abc");

    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { fetchHealth } = await import("./client");
    await fetchHealth();

    expect(fetchMock).toHaveBeenCalled();
    const [, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-abc");
    expect(String(fetchMock.mock.calls[0]![0])).toContain(resolveApiBase());
  });

  it("clears token on 401", async () => {
    const { setAuthToken, getAuthToken, ApiError, fetchHealth } = await import("./client");
    setAuthToken("will-clear");
    expect(getAuthToken()).toBe("will-clear");

    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unauthorized" }), { status: 401 }),
    );

    await expect(fetchHealth()).rejects.toBeInstanceOf(ApiError);
    expect(getAuthToken()).toBeNull();
    expect(sessionStorage.getItem("be_auth_token")).toBeNull();
  });

  it("preserves token on 403", async () => {
    const { setAuthToken, getAuthToken, ApiError, fetchHealth } = await import("./client");
    setAuthToken("keep-me");

    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Forbidden" }), { status: 403 }),
    );

    const err = await fetchHealth().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as InstanceType<typeof ApiError>).status).toBe(403);
    expect((err as InstanceType<typeof ApiError>).userMessage).toBe("Forbidden");
    expect(getAuthToken()).toBe("keep-me");
    expect(sessionStorage.getItem("be_auth_token")).toBe("keep-me");
  });

  it("exposes human detail without raw HTTP JSON dump", async () => {
    const { ApiError, formatApiError, fetchHealth } = await import("./client");
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Cannot approve blocked decision with open dependency blockers" }),
        { status: 422 },
      ),
    );
    const err = await fetchHealth().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(formatApiError(err)).toBe(
      "Cannot approve blocked decision with open dependency blockers",
    );
    expect(formatApiError(err)).not.toMatch(/^HTTP 422:/);
  });
});
