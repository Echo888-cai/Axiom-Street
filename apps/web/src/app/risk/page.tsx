import { PhasePlaceholder } from "@/components/phase-placeholder";

export default function RiskPage() {
  return (
    <PhasePlaceholder
      title="风控"
      phase="第四–五阶段"
      description="风险监控、告警，以及独立于策略的风控引擎。"
      items={["仓位与回撤硬限制", "AI 不能修改系统风控", "告警与停机审计"]}
    />
  );
}
