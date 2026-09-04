from __future__ import annotations

from pathlib import Path
from typing import Any

import jedi

from services.api.schemas import (
    LspCompleteOut,
    LspCompletion,
    LspHoverOut,
)
from services.api.services.syntax import check_python

jedi.settings.use_filesystem_cache = False

_STUBS = Path(__file__).resolve().parents[3] / "quant" / "lsp_stubs"

_KIND = {
    "function": "function",
    "class": "class",
    "module": "module",
    "instance": "variable",
    "keyword": "keyword",
    "statement": "variable",
    "param": "variable",
    "property": "property",
}


def _script(code: str):
    project = jedi.Project(path=str(_STUBS), added_sys_path=[str(_STUBS)])
    return jedi.Script(code, path="strategy.py", project=project)


def complete_python(code: str, line: int, column: int) -> LspCompleteOut:
    syntax = check_python(code)
    try:
        script = _script(code)
        raw = script.complete(line, column)
    except Exception as exc:  # noqa: BLE001 - Jedi can raise on broken buffers
        return LspCompleteOut(items=[], syntax=syntax, error=str(exc))
    items: list[LspCompletion] = []
    for item in raw[:80]:
        name = item.name
        if name.startswith("__") and name not in {"__init__", "__enter__", "__exit__"}:
            continue
        doc = (item.docstring(raw=True) or "").strip()
        items.append(
            LspCompletion(
                label=name,
                insert=item.complete or name,
                kind=_KIND.get(item.type, "variable"),
                detail=(doc.splitlines()[0] if doc else item.type)[:240],
            )
        )
    return LspCompleteOut(items=items, syntax=syntax)


def hover_python(code: str, line: int, column: int) -> LspHoverOut:
    try:
        script = _script(code)
        helps = script.help(line, column)
    except Exception as exc:  # noqa: BLE001
        return LspHoverOut(contents=None, error=str(exc))
    if not helps:
        return LspHoverOut(contents=None)
    chunks: list[str] = []
    for item in helps[:3]:
        doc = (item.docstring() or "").strip()
        title = getattr(item, "name", "") or ""
        if title and doc:
            chunks.append(f"{title}\n{doc}")
        elif doc:
            chunks.append(doc)
        elif title:
            chunks.append(title)
    contents = "\n\n".join(chunks).strip() or None
    return LspHoverOut(contents=contents)


def diagnostics_python(code: str) -> dict[str, Any]:
    syntax = check_python(code)
    return {"syntax": syntax.model_dump()}
