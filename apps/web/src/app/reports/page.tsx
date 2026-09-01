import { PhasePlaceholder } from "@/components/phase-placeholder";

export default function ReportsPage() {
  return (
    <PhasePlaceholder
      title="报告"
      phase="第二阶段及以后"
      description="AI 研究报告与策略复盘文档。"
      items={["回测复盘", "失效模式记录", "可导出的研究笔记"]}
    />
  );
}
