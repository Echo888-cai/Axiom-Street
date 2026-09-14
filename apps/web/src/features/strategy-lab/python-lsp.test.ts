import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  disposePythonLanguageFeatures,
  replacePythonLanguageFeatures,
} from "./python-lsp";

function monaco(disposables: Array<{ dispose: () => void }>) {
  return {
    languages: {
      registerCompletionItemProvider: vi.fn(() => {
        const d = { dispose: vi.fn() };
        disposables.push(d);
        return d;
      }),
      registerHoverProvider: vi.fn(() => {
        const d = { dispose: vi.fn() };
        disposables.push(d);
        return d;
      }),
    },
  } as never;
}

describe("Python LSP lifecycle (P1.4b)", () => {
  beforeEach(() => {
    disposePythonLanguageFeatures();
  });

  it("replacing disposes the previous registration instead of leaking it", () => {
    const first: Array<{ dispose: () => void }> = [];
    const second: Array<{ dispose: () => void }> = [];
    replacePythonLanguageFeatures(monaco(first));
    expect(first).toHaveLength(2);
    replacePythonLanguageFeatures(monaco(second));
    for (const d of first) expect(d.dispose).toHaveBeenCalledTimes(1);
    expect(second).toHaveLength(2);
  });

  it("unmount dispose is idempotent and clears ownership", () => {
    const created: Array<{ dispose: () => void }> = [];
    replacePythonLanguageFeatures(monaco(created));
    disposePythonLanguageFeatures();
    disposePythonLanguageFeatures();
    for (const d of created) expect(d.dispose).toHaveBeenCalledTimes(1);
  });

  it("replace after dispose registers fresh providers", () => {
    const created: Array<{ dispose: () => void }> = [];
    replacePythonLanguageFeatures(monaco([]));
    disposePythonLanguageFeatures();
    replacePythonLanguageFeatures(monaco(created));
    expect(created).toHaveLength(2);
    disposePythonLanguageFeatures();
  });
});
