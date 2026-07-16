/**
 * Pure helper functions with no vscode dependency.
 * Importable from both the extension (with vscode available) and unit tests (Node only).
 */
import * as path from "path";

/** Schemes that are never user files. */
export const SKIP_SCHEMES = new Set([
  "git",
  "extension-output",
  "output",
  "debug",
]);

/** Path segments that indicate non-user files. */
export const SKIP_PATH_SEGMENTS = [".git", "node_modules"];

/**
 * Returns true when the file at `fsPath` (with the given URI `scheme`)
 * should be silently ignored.
 */
export function shouldSkipPath(fsPath: string, scheme = "file"): boolean {
  if (SKIP_SCHEMES.has(scheme)) {
    return true;
  }

  const normalised = fsPath.replace(/\\/g, "/");
  const segments = normalised.split("/");

  for (const seg of SKIP_PATH_SEGMENTS) {
    if (segments.includes(seg)) {
      return true;
    }
  }

  return false;
}

/**
 * Makes `fsPath` relative to `workspaceRoot` when possible,
 * using forward slashes. Falls back to the absolute path.
 */
export function relativise(fsPath: string, workspaceRoot: string): string {
  if (!workspaceRoot) {
    return fsPath;
  }
  const rel = path.relative(workspaceRoot, fsPath);
  // path.relative returns paths starting with ".." when outside the root
  if (rel.startsWith("..")) {
    return fsPath;
  }
  return rel.replace(/\\/g, "/");
}
