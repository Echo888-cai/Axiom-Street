import { PhasePlaceholder } from "@/components/phase-placeholder";

export default function LivePage() {
  return (
    <PhasePlaceholder
      title="实盘"
      phase="第五阶段"
      description="仅在模拟盘稳定后开放：硬风控、一键停机与订单对账。"
      items={["人工确认后才能上线", "风险引擎独立于策略代码", "对账失败则停止发单"]}
    />
  );
}
