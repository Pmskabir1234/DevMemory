import { DevMemEvent } from "./eventBuilder";

/** Pause for `ms` milliseconds. */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * POST `payload` to `${backendUrl}/api/events`.
 * Retries up to `retries` times with `retryDelayMs` between attempts (default 1 s).
 * Never throws — logs errors to console.error.
 */
export async function sendEvent(
  payload: DevMemEvent,
  backendUrl: string,
  retries = 3,
  retryDelayMs = 1000
): Promise<void> {
  const url = `${backendUrl.replace(/\/$/, "")}/api/events`;
  const body = JSON.stringify(payload);

  let lastError: unknown;

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Success — return early
      return;
    } catch (err) {
      lastError = err;
      if (attempt < retries) {
        await sleep(retryDelayMs);
      }
    }
  }

  // All retries exhausted
  console.error(
    `[devmem] Failed to send event after ${retries} attempt(s):`,
    lastError
  );
}
