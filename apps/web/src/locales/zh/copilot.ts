export const copilot = {
  title: "Copilot 上下文",
  subtitle: "只读事实 · AI 不改动研究状态",
  version: "版本",
  trials: {
    title: "试验台账",
    total: "此策略试验总数",
    section: "按数据快照",
    duplicate: "重复参数",
    superseded: "已被新快照取代",
    none: "尚无试验",
  },
  gates: {
    title: "验证闸门",
    passed: "通过",
    failed: "未通过",
    running: "进行中",
    none: "尚无验证记录",
  },
  empty: {
    title: "此页面没有研究上下文",
    description:
      "打开一个策略或回测详情页后,这里会显示该策略在各数据快照上的试验次数、重复参数与最新验证闸门结果——全部是只读事实。Copilot 不做策略生成,也不会改动验证状态。",
  },
  notFound: {
    title: "无法读取研究上下文",
    description: "资源不存在或已被删除,上下文已为空。",
  },
} as const;
