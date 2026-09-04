import type { editor, languages } from "monaco-editor";
import { api, type LspCompletion } from "@/lib/api";

function completionKind(
  monacoApi: typeof import("monaco-editor"),
  kind: string,
): languages.CompletionItemKind {
  const map: Record<string, languages.CompletionItemKind> = {
    function: monacoApi.languages.CompletionItemKind.Function,
    class: monacoApi.languages.CompletionItemKind.Class,
    module: monacoApi.languages.CompletionItemKind.Module,
    variable: monacoApi.languages.CompletionItemKind.Variable,
    keyword: monacoApi.languages.CompletionItemKind.Keyword,
    property: monacoApi.languages.CompletionItemKind.Property,
  };
  return map[kind] ?? monacoApi.languages.CompletionItemKind.Text;
}

export function registerPythonLanguageFeatures(
  monacoApi: typeof import("monaco-editor"),
): { dispose: () => void } {
  const completion = monacoApi.languages.registerCompletionItemProvider("python", {
    triggerCharacters: [".", "_"],
    provideCompletionItems: async (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      try {
        const result = await api.completePython(model.getValue(), position.lineNumber, position.column - 1);
        const suggestions: languages.CompletionItem[] = result.items.map((item: LspCompletion) => ({
          label: item.label,
          kind: completionKind(monacoApi, item.kind),
          insertText: item.insert || item.label,
          detail: item.detail || undefined,
          range,
        }));
        return { suggestions };
      } catch {
        return { suggestions: [] };
      }
    },
  });
  const hover = monacoApi.languages.registerHoverProvider("python", {
    provideHover: async (model, position) => {
      try {
        const result = await api.hoverPython(model.getValue(), position.lineNumber, position.column - 1);
        if (!result.contents) return null;
        return {
          contents: [{ value: result.contents }],
        };
      } catch {
        return null;
      }
    },
  });
  return {
    dispose: () => {
      completion.dispose();
      hover.dispose();
    },
  };
}

export function applyEngineError(
  monacoApi: typeof import("monaco-editor"),
  editorInstance: editor.IStandaloneCodeEditor,
  error: { message?: string; line?: number } | null,
) {
  const model = editorInstance.getModel();
  if (!model) return;
  monacoApi.editor.setModelMarkers(
    model,
    "axiom-engine",
    error?.line
      ? [
          {
            startLineNumber: error.line,
            startColumn: 1,
            endLineNumber: error.line,
            endColumn: 120,
            message: error.message || "回测失败",
            severity: monacoApi.MarkerSeverity.Error,
          },
        ]
      : [],
  );
}
