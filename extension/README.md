# Developer Memory OS — VS Code Extension

Captures editor activity (file opens, saves, closes, diagnostics, workspace events) and sends them to the Developer Memory OS backend.

---

## Requirements

- VS Code `^1.85.0`
- Node.js `18+` (for built-in `fetch`)
- Developer Memory OS backend running (default: `http://127.0.0.1:8000`)

---

## Installation (development)

```bash
cd extension
npm install
npm run compile
```

Then press **F5** in VS Code to launch the Extension Development Host, or use `vsce package` to build a `.vsix` file and install it via *Extensions → Install from VSIX*.

---

## Configuration

| Setting | Type | Default | Description |
|---|---|---|---|
| `devmem.backendUrl` | `string` | `http://127.0.0.1:8000` | Base URL of the Developer Memory OS backend |

Change in VS Code settings (`Ctrl+,`) or in `settings.json`:

```json
{
  "devmem.backendUrl": "http://my-server:8000"
}
```

---

## Usage

The extension activates automatically when VS Code loads any workspace (`onStartupFinished`). Once active:

- A **`$(database) devmem`** item appears in the status bar.
- Click it (or run **DevMem: Show Status** from the Command Palette) to see the configured backend URL and confirm the extension is running.
- All events are posted silently to `POST /api/events` — no popups.

### Events captured

| Event | Trigger |
|---|---|
| `WorkspaceOpened` | Extension activates with an open workspace folder |
| `FileOpened` | A text document is opened |
| `FileSaved` | A text document is saved |
| `FileClosed` | A text document is closed |
| `Diagnostic` | A file has Error or Warning diagnostics |
| `WorkspaceClosed` | A workspace folder is removed |

### Filtered out

- URI schemes: `git`, `extension-output`, `output`, `debug`
- Files inside `.git/` or `node_modules/`

---

## Running tests

```bash
npm run compile
npm test
```

Tests cover filter logic, relative-path computation, and HTTP retry behaviour (no VS Code instance required).

---

## Project structure

```
extension/
  src/
    extension.ts    — activation, event subscriptions, status bar
    client.ts       — HTTP POST with 3-retry logic
    eventBuilder.ts — builds typed event payloads
    filter.ts       — skips non-user files
  test/
    extension.test.ts — unit tests (Mocha + assert)
    runTests.ts       — lightweight Mocha runner
  package.json
  tsconfig.json
  .vscodeignore
  README.md
```
