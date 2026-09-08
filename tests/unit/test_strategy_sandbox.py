from __future__ import annotations

import pytest

from quant.security.sandbox import (
    StrategySandboxViolation,
    docker_security_args,
    validate_strategy_source,
)


def test_algorithm_imports_and_safe_stdlib_are_allowed():
    validate_strategy_source(
        "from AlgorithmImports import *\nimport math\nfrom datetime import date\nclass Demo: pass\n"
    )


@pytest.mark.parametrize(
    "source",
    [
        "import os\n",
        "from subprocess import run\n",
        "import socket\n",
        "open('/etc/passwd')\n",
        "eval('1 + 1')\n",
        "exec('x = 1')\n",
    ],
)
def test_dangerous_imports_and_calls_are_rejected(source: str):
    with pytest.raises(StrategySandboxViolation, match="strategy_sandbox_violation"):
        validate_strategy_source(source)


def test_syntax_errors_are_reported_as_sandbox_violations():
    with pytest.raises(StrategySandboxViolation, match="第 1 行"):
        validate_strategy_source("class Broken(\n")


def test_docker_security_args_are_explicit_and_non_root():
    args = docker_security_args("1000:1000")

    assert "--network" in args and args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert "--user" in args and args[args.index("--user") + 1] == "1000:1000"
    assert "--cap-drop" in args and args[args.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in args
    assert "no-new-privileges=true" in args
    assert "seccomp=default" in args
    assert "--tmpfs" in args
