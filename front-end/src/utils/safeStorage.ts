let hasWarned = false;

const warnOnce = (error: unknown) => {
  if (hasWarned) return;
  hasWarned = true;
  console.warn(
    "Local storage unavailable; falling back to in-memory state only.",
    error
  );
};

export const safeLocalStorage = {
  getItem(key: string): string | null {
    if (typeof window === "undefined") return null;
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      warnOnce(error);
      return null;
    }
  },
  setItem(key: string, value: string): void {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      warnOnce(error);
    }
  },
  removeItem(key: string): void {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.removeItem(key);
    } catch (error) {
      warnOnce(error);
    }
  },
};
