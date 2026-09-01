import { PhasePlaceholder } from "@/components/phase-placeholder";

export default function PaperPage() {
  return (
    <PhasePlaceholder
      title="模拟交易"
      phase="第四阶段"
      description="Alpaca 模拟盘部署：持仓、订单、成交与盈亏。"
      items={["独立于回测的实时账户视图", "与回测结果对照，而不是替代", "一键停机预演"]}
    />
  );
}
