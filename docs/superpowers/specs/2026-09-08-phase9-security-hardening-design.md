# Phase 9 安全加固规格

## 目标

把回测执行边界从“已有网络隔离和资源限制”提升为可验证的沙箱约束，并在写入 LEAN 容器前拒绝明显的宿主机访问与代码执行逃逸方式。

## 安全边界

- LEAN 冷启动和 warm slot 使用同一组安全参数：无网络、非 root、丢弃 Linux capabilities、禁止提权、只读根文件系统、默认 seccomp、受限 `/tmp`。
- 数据快照和算法源码仍只读挂载；结果目录是唯一需要写入的宿主机目录。
- 策略源码在宿主机落盘前做 AST 检查；禁止 `os`、`sys`、`subprocess`、网络、动态导入、文件读写和 `eval/exec/compile` 等高风险能力。
- 违规必须返回稳定的 `strategy_sandbox_violation` 错误，不执行 Docker，不写入算法目录。
- 不添加任何真实 Broker、密钥读取或 Live 下单能力。

## 验收标准

1. 安全参数由一个纯函数生成，冷启动和 warm slot 都调用它。
2. 安全策略测试覆盖网络、只读根、非 root、cap drop、no-new-privileges、seccomp、tmpfs。
3. AST 检查覆盖危险 import、危险调用、语法错误和允许的 `AlgorithmImports`。
4. 现有回测、风险门和前端测试不回归。
