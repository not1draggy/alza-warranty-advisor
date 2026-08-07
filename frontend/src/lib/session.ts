const STORAGE_KEY = "warranty-advisor-session";

/**
 * Anonymous visitors get a locally generated id so their search history follows
 * them without an account. It is opaque and contains nothing about the visitor.
 */
export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) return existing;
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36);
  window.localStorage.setItem(STORAGE_KEY, id);
  return id;
}
