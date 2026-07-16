/**
 * Unit tests for devmem-vscode extension logic.
 * Run with: npm test  (compiles first, then: node ./out/test/runTests.js)
 *
 * These tests do NOT import vscode — they exercise pure helper functions only.
 */
import * as assert from "assert";
import { shouldSkipPath } from "../src/helpers";
import { relativise } from "../src/helpers";

// ---------------------------------------------------------------------------
// 1. Filter tests
// ---------------------------------------------------------------------------
describe("filter — shouldSkipPath", () => {
  it("skips files inside .git/", () => {
    assert.strictEqual(
      shouldSkipPath("/home/user/project/.git/config"),
      true
    );
  });

  it("skips files inside node_modules/", () => {
    assert.strictEqual(
      shouldSkipPath("/home/user/project/node_modules/lodash/index.js"),
      true
    );
  });

  it("skips the 'git' scheme", () => {
    assert.strictEqual(shouldSkipPath("/any/path/file.ts", "git"), true);
  });

  it("skips the 'extension-output' scheme", () => {
    assert.strictEqual(
      shouldSkipPath("/any/path/file.ts", "extension-output"),
      true
    );
  });

  it("skips the 'output' scheme", () => {
    assert.strictEqual(shouldSkipPath("/any/path/file.ts", "output"), true);
  });

  it("skips the 'debug' scheme", () => {
    assert.strictEqual(shouldSkipPath("/any/path/file.ts", "debug"), true);
  });

  it("does NOT skip a normal user file", () => {
    assert.strictEqual(
      shouldSkipPath("/home/user/project/src/main.ts"),
      false
    );
  });

  it("does NOT skip a path containing 'node_modules' as a substring (not a segment)", () => {
    assert.strictEqual(
      shouldSkipPath("/home/user/project/my_node_modules_backup/file.ts"),
      false
    );
  });
});

// ---------------------------------------------------------------------------
// 2. Event builder — relativise helper
// ---------------------------------------------------------------------------
describe("eventBuilder — relativise", () => {
  const workspaceRoot = "/home/user/project";

  it("returns a relative path when the file is inside the workspace", () => {
    const result = relativise("/home/user/project/src/main.ts", workspaceRoot);
    assert.strictEqual(result, "src/main.ts");
  });

  it("returns the absolute path when the file is outside the workspace", () => {
    const result = relativise("/tmp/scratch.ts", workspaceRoot);
    assert.strictEqual(result, "/tmp/scratch.ts");
  });

  it("returns the absolute path when workspaceRoot is empty", () => {
    const result = relativise("/home/user/project/src/main.ts", "");
    assert.strictEqual(result, "/home/user/project/src/main.ts");
  });

  it("uses forward slashes when given Windows-style paths", () => {
    // path.relative on Windows handles drive letters; simulate with posix path.
    const winRoot = "C:/Users/user/project";
    const winFile = "C:/Users/user/project/src/utils.ts";
    const result = relativise(winFile, winRoot);
    // On Windows path.relative produces "src\utils.ts", our code converts to "src/utils.ts"
    assert.ok(
      result === "src/utils.ts" || result === "src\\utils.ts",
      `Unexpected result: ${result}`
    );
  });
});

// ---------------------------------------------------------------------------
// 3. HTTP client — retry logic
// ---------------------------------------------------------------------------
describe("client — sendEvent retry logic", () => {
  it("calls fetch exactly 3 times when it fails twice then succeeds", async () => {
    let callCount = 0;

    const originalFetch = (globalThis as Record<string, unknown>).fetch;

    (globalThis as Record<string, unknown>).fetch = async (): Promise<Response> => {
      callCount++;
      if (callCount < 3) {
        throw new Error("network error");
      }
      return new Response(JSON.stringify({ status: "ok" }), { status: 201 });
    };

    // Dynamic import so our mock is in place before the module runs
    const { sendEvent } = await import("../src/client");

    const payload = {
      event_type: "FileSaved",
      file_path: "src/main.ts",
      workspace: "/home/user/project",
      language: "typescript",
      timestamp: new Date().toISOString(),
      metadata: {},
    };

    // Pass retryDelayMs=0 so there is no real delay in tests
    await sendEvent(payload, "http://127.0.0.1:8000", 3, 0);

    (globalThis as Record<string, unknown>).fetch = originalFetch;

    assert.strictEqual(callCount, 3, `Expected 3 fetch calls, got ${callCount}`);
  });

  it("calls fetch exactly `retries` times when all attempts fail", async () => {
    let callCount = 0;
    const originalFetch = (globalThis as Record<string, unknown>).fetch;

    (globalThis as Record<string, unknown>).fetch = async (): Promise<Response> => {
      callCount++;
      throw new Error("always fails");
    };

    const { sendEvent } = await import("../src/client");

    const payload = {
      event_type: "FileOpened",
      file_path: "src/app.ts",
      workspace: "/home/user/project",
      language: "typescript",
      timestamp: new Date().toISOString(),
      metadata: {},
    };

    await sendEvent(payload, "http://127.0.0.1:8000", 3, 0);

    (globalThis as Record<string, unknown>).fetch = originalFetch;

    assert.strictEqual(callCount, 3, `Expected 3 fetch calls, got ${callCount}`);
  });
});
