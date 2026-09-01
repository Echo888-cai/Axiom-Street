import { PhasePlaceholder } from "@/components/phase-placeholder";

export default function ExperimentsPage() {
  return (
    <PhasePlaceholder
      title="实验"
      phase="第三阶段及以后"
      description="变体对比，以及将优秀变体提升为正式策略版本。"
      items={["参数扫描不替代验证", "Walk-forward 与样本外", "把赢家提升为正式版本"]}
    />
  );
}
