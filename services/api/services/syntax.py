from __future__ import annotations

import ast

from services.api.schemas import SyntaxCheckOut


def check_python(code: str) -> SyntaxCheckOut:
    if not code.strip():
        return SyntaxCheckOut(ok=False, message="代码为空", line=1, column=1)
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return SyntaxCheckOut(
            ok=False,
            message=exc.msg or "语法错误",
            line=exc.lineno,
            column=exc.offset,
        )
    return SyntaxCheckOut(ok=True)
