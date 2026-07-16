import * as vscode from "vscode";
import { relativise } from "./helpers";

export { relativise } from "./helpers";

export interface DevMemEvent {
  event_type: string;
  file_path: string | null;
  workspace: string;
  language: string | null;
  timestamp: string;
  metadata: Record<string, unknown>;
}

/** Returns the first workspace root fsPath, or "" if no workspace is open. */
function getWorkspaceRoot(): string {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length > 0 ? folders[0].uri.fsPath : "";
}

/** Build an event payload for file-level events (open / save / close). */
export function buildFileEvent(
  eventType: "FileOpened" | "FileSaved" | "FileClosed",
  document: vscode.TextDocument
): DevMemEvent {
  const workspaceRoot = getWorkspaceRoot();
  return {
    event_type: eventType,
    file_path: relativise(document.uri.fsPath, workspaceRoot),
    workspace: workspaceRoot,
    language: document.languageId,
    timestamp: new Date().toISOString(),
    metadata: {},
  };
}

/** Build one event payload per diagnostic (Error / Warning) for a changed URI. */
export function buildDiagnosticEvents(
  uri: vscode.Uri,
  diagnostics: readonly vscode.Diagnostic[]
): DevMemEvent[] {
  const workspaceRoot = getWorkspaceRoot();
  const events: DevMemEvent[] = [];

  for (const diag of diagnostics) {
    if (
      diag.severity !== vscode.DiagnosticSeverity.Error &&
      diag.severity !== vscode.DiagnosticSeverity.Warning
    ) {
      continue;
    }

    const severity =
      diag.severity === vscode.DiagnosticSeverity.Error ? "Error" : "Warning";

    events.push({
      event_type: "Diagnostic",
      file_path: relativise(uri.fsPath, workspaceRoot),
      workspace: workspaceRoot,
      language: null,
      timestamp: new Date().toISOString(),
      metadata: {
        severity,
        message: diag.message,
        source: diag.source ?? "",
      },
    });
  }

  return events;
}

/** Build an event payload for workspace open / close events. */
export function buildWorkspaceEvent(
  eventType: "WorkspaceOpened" | "WorkspaceClosed",
  folderPath: string
): DevMemEvent {
  const workspaceRoot = getWorkspaceRoot();
  return {
    event_type: eventType,
    file_path: null,
    workspace: workspaceRoot || folderPath,
    language: null,
    timestamp: new Date().toISOString(),
    metadata: { folder: folderPath },
  };
}
