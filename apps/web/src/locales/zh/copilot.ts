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
  insight: {
    title: "Copilot 评估",
    boundary: "仅聚合统计出站:策略源码、参数与行情永不外发",
    disabled:
      "模型评估未启用:在服务端配置 API key 后,Copilot 会依据试验台账与闸门事实,诚实判断是否该停",
    idle: "还没有评估记录。Copilot 会基于试验台账与闸门结果判断:该停了吗?",
    evaluate: "让 Copilot 评估一下",
    reevaluate: "重新评估",
    evaluating: "评估中,通常几秒…",
    retry: "重试",
    failed: "这次评估失败了",
    retryHint: "可重试一次;若持续失败,多半是模型服务或账户问题",
    model: "模型",
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
