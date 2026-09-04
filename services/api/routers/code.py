from __future__ import annotations

from fastapi import APIRouter

from services.api.schemas import (
    LspCompleteOut,
    LspHoverOut,
    LspPositionIn,
    SyntaxCheckIn,
    SyntaxCheckOut,
)
from services.api.services.lsp import complete_python, hover_python
from services.api.services.syntax import check_python

router = APIRouter(prefix="/code", tags=["code"])


@router.post("/syntax", response_model=SyntaxCheckOut)
def python_syntax(payload: SyntaxCheckIn) -> SyntaxCheckOut:
    return check_python(payload.code)


@router.post("/complete", response_model=LspCompleteOut)
def python_complete(payload: LspPositionIn) -> LspCompleteOut:
    return complete_python(payload.code, payload.line, payload.column)


@router.post("/hover", response_model=LspHoverOut)
def python_hover(payload: LspPositionIn) -> LspHoverOut:
    return hover_python(payload.code, payload.line, payload.column)
