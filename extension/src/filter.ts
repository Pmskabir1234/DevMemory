import * as vscode from "vscode";
import { shouldSkipPath } from "./helpers";

export { shouldSkipPath } from "./helpers";

/**
 * Returns true when the document should be silently ignored.
 * Filters out:
 *  - Non-user URI schemes (git, output, debug, …)
 *  - Files inside .git/ or node_modules/
 */
export function shouldSkip(document: vscode.TextDocument): boolean {
  return shouldSkipPath(document.uri.fsPath, document.uri.scheme);
}
