import * as vscode from "vscode";
import { shouldSkip } from "./filter";
import {
  buildFileEvent,
  buildDiagnosticEvents,
  buildWorkspaceEvent,
} from "./eventBuilder";
import { sendEvent } from "./client";

/** Read the configured backend URL from VS Code settings. */
function getBackendUrl(): string {
  return (
    vscode.workspace
      .getConfiguration("devmem")
      .get<string>("backendUrl", "http://127.0.0.1:8000")
      .replace(/\/$/, "") || "http://127.0.0.1:8000"
  );
}

export function activate(context: vscode.ExtensionContext): void {
  // ── Status bar item ─────────────────────────────────────────────────────
  const statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBar.text = "$(database) devmem";
  statusBar.tooltip = "Developer Memory OS — click for status";
  statusBar.command = "devmem.showStatus";
  statusBar.show();

  // ── Show Status command ──────────────────────────────────────────────────
  const showStatusCmd = vscode.commands.registerCommand(
    "devmem.showStatus",
    () => {
      const url = getBackendUrl();
      vscode.window.showInformationMessage(
        `Developer Memory OS\nBackend URL: ${url}\nStatus: active`
      );
    }
  );

  // ── WorkspaceOpened — fire once on activation ────────────────────────────
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length > 0) {
    const backendUrl = getBackendUrl();
    const event = buildWorkspaceEvent("WorkspaceOpened", folders[0].uri.fsPath);
    sendEvent(event, backendUrl).catch(() => {
      // already handled inside sendEvent
    });
  }

  // ── FileOpened ───────────────────────────────────────────────────────────
  const onOpen = vscode.workspace.onDidOpenTextDocument((document) => {
    try {
      if (shouldSkip(document)) {
        return;
      }
      const event = buildFileEvent("FileOpened", document);
      sendEvent(event, getBackendUrl()).catch(() => {});
    } catch (err) {
      console.error("[devmem] onDidOpenTextDocument error:", err);
    }
  });

  // ── FileSaved ────────────────────────────────────────────────────────────
  const onSave = vscode.workspace.onDidSaveTextDocument((document) => {
    try {
      if (shouldSkip(document)) {
        return;
      }
      const event = buildFileEvent("FileSaved", document);
      sendEvent(event, getBackendUrl()).catch(() => {});
    } catch (err) {
      console.error("[devmem] onDidSaveTextDocument error:", err);
    }
  });

  // ── FileClosed ───────────────────────────────────────────────────────────
  const onClose = vscode.workspace.onDidCloseTextDocument((document) => {
    try {
      if (shouldSkip(document)) {
        return;
      }
      const event = buildFileEvent("FileClosed", document);
      sendEvent(event, getBackendUrl()).catch(() => {});
    } catch (err) {
      console.error("[devmem] onDidCloseTextDocument error:", err);
    }
  });

  // ── Diagnostics ──────────────────────────────────────────────────────────
  const onDiagnostics = vscode.languages.onDidChangeDiagnostics((e) => {
    try {
      const backendUrl = getBackendUrl();
      for (const uri of e.uris) {
        const diagnostics = vscode.languages.getDiagnostics(uri);
        const events = buildDiagnosticEvents(uri, diagnostics);
        for (const evt of events) {
          sendEvent(evt, backendUrl).catch(() => {});
        }
      }
    } catch (err) {
      console.error("[devmem] onDidChangeDiagnostics error:", err);
    }
  });

  // ── WorkspaceClosed ──────────────────────────────────────────────────────
  const onWorkspaceChange = vscode.workspace.onDidChangeWorkspaceFolders(
    (e) => {
      try {
        const backendUrl = getBackendUrl();
        for (const folder of e.removed) {
          const event = buildWorkspaceEvent(
            "WorkspaceClosed",
            folder.uri.fsPath
          );
          sendEvent(event, backendUrl).catch(() => {});
        }
      } catch (err) {
        console.error("[devmem] onDidChangeWorkspaceFolders error:", err);
      }
    }
  );

  // ── Register all disposables ─────────────────────────────────────────────
  context.subscriptions.push(
    statusBar,
    showStatusCmd,
    onOpen,
    onSave,
    onClose,
    onDiagnostics,
    onWorkspaceChange
  );
}

export function deactivate(): void {
  // All disposables are cleaned up via context.subscriptions
}
