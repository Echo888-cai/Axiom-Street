import { request } from "./http";
import type { LspCompletion } from "./types";

export const codeApi = {
  checkSyntax: (code: string) =>
    request<{
      ok: boolean;
      message: string | null;
      line: number | null;
      column: number | null;
    }>("/api/v1/code/syntax", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  completePython: (code: string, line: number, column: number) =>
    request<{
      items: LspCompletion[];
      syntax: { ok: boolean };
      error?: string | null;
    }>("/api/v1/code/complete", {
      method: "POST",
      body: JSON.stringify({ code, line, column }),
    }),
  hoverPython: (code: string, line: number, column: number) =>
    request<{ contents: string | null; error?: string | null }>(
      "/api/v1/code/hover",
      {
        method: "POST",
        body: JSON.stringify({ code, line, column }),
      },
    ),
};
