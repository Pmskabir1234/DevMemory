/**
 * Minimal test runner — runs Mocha directly on the compiled test files
 * without needing @vscode/test-electron (which requires an actual VS Code install).
 *
 * Usage: node ./out/test/runTests.js
 */
import * as path from "path";
import Mocha from "mocha";

const mocha = new Mocha({ ui: "bdd", timeout: 10_000 });
mocha.addFile(path.resolve(__dirname, "extension.test.js"));

mocha.run((failures) => {
  process.exitCode = failures ? 1 : 0;
});
