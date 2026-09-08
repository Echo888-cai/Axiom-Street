# Phase 9 Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 LEAN 执行容器和策略源码增加可测试、默认启用的安全边界。

**Architecture:** `quant/security/sandbox.py` 只负责纯安全策略：生成 Docker flags 和检查策略 AST。`LeanQuantEngine` 与 `LeanSlotPool` 只消费这些结果，不自行拼接安全规则。违规在 host 侧于创建 job 目录前抛出稳定错误。

**Tech Stack:** Python 3.11、ast、Docker CLI、pytest、Ruff、mypy。

**Spec:** `docs/superpowers/specs/2026-09-08-phase9-security-hardening-design.md`

## Global Constraints

- 不引入新运行时依赖。
- 安全参数默认启用；只允许通过显式环境变量配置容器用户，不允许默认 root。
- 不实现真实 Broker、真实订单或 Live 开关放行。
- 每个任务先写失败测试，再实现，再运行聚焦测试。

### Task 1: 策略源码沙箱检查器

**Files:**
- Create: `quant/security/__init__.py`
- Create: `quant/security/sandbox.py`
- Test: `tests/unit/test_strategy_sandbox.py`

**Interfaces:**
- Produces `validate_strategy_source(source: str) -> None` and `docker_security_args(container_user: str | None = None) -> list[str]`.
- Raises `StrategySandboxViolation` with `code == "strategy_sandbox_violation"` and a line-aware message.

- [ ] Step 1: Write tests for allowed `from AlgorithmImports import *`, forbidden imports/calls, syntax errors, and all Docker hardening flags.
- [ ] Step 2: Run `pytest tests/unit/test_strategy_sandbox.py -q` and verify failure because the module does not exist.
- [ ] Step 3: Implement AST validation and deterministic Docker flag generation.
- [ ] Step 4: Run the focused test and `ruff check quant/security tests/unit/test_strategy_sandbox.py`.
- [ ] Step 5: Commit `feat: add strategy sandbox policy`.

### Task 2: Wire the policy into cold and warm LEAN execution

**Files:**
- Modify: `quant/engine/lean.py`
- Modify: `quant/engine/pool.py`
- Modify: `tests/unit/test_universe_pit.py` or a new engine command test

**Interfaces:**
- Both launch paths call `docker_security_args()`.
- `LeanQuantEngine.run_backtest` calls `validate_strategy_source` before creating the job directory.

- [ ] Step 1: Add failing tests that inspect cold command construction and reject unsafe strategy code before Docker is invoked.
- [ ] Step 2: Run the focused tests and verify failure.
- [ ] Step 3: Apply the shared flags to `docker run` in `lean.py` and warm slot startup in `pool.py`; call the validator before filesystem writes.
- [ ] Step 4: Run focused engine tests plus `pytest tests/unit/test_strategy_sandbox.py -q`.
- [ ] Step 5: Commit `feat: harden lean execution sandbox`.

### Task 3: Documentation and full verification

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/PLAN.md`

- [ ] Step 1: Document the enforced flags, source validator, and explicit non-goal of Broker integration.
- [ ] Step 2: Run `make test-all`.
- [ ] Step 3: Commit `docs: document phase 9 sandbox hardening`.
