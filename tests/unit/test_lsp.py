from __future__ import annotations

from quant.engine.errors import strategy_error_location
from services.api.services.lsp import complete_python, hover_python
from services.api.services.syntax import check_python


def test_complete_qcalgorithm_methods():
    code = (
        "from AlgorithmImports import *\n\n"
        "class A(QCAlgorithm):\n"
        "    def Initialize(self):\n"
        "        self.\n"
    )
    line = 5
    column = len(code.splitlines()[line - 1])
    result = complete_python(code, line=line, column=column)
    labels = {item.label for item in result.items}
    assert labels, result.error
    assert any(name in labels for name in ("SetStartDate", "SetCash", "SetHoldings", "AddEquity"))


def test_hover_on_builtin():
    code = "x = abs(1)\n"
    result = hover_python(code, line=1, column=5)
    assert result.contents is None or "abs" in (result.contents or "")


def test_syntax_still_fail_loud():
    out = check_python("def broken(:\n")
    assert out.ok is False
    assert out.line is not None


def test_strategy_error_location_uses_last_frame():
    message = '''Traceback (most recent call last):
  File "/Lean/Algorithm.Python/strategy.py", line 12, in Initialize
    self.foo()
  File "/Lean/Algorithm.Python/strategy.py", line 44, in OnData
    x = missing
NameError: name 'missing' is not defined
'''
    assert strategy_error_location(message) == 44
    assert strategy_error_location("docker failed") is None
