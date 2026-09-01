import {
  Beaker,
  FileBarChart2,
  FlaskConical,
  Home,
  Layers,
  LineChart,
  Newspaper,
  Settings,
  Shield,
  Workflow,
} from "lucide-react";

export const NAV_ITEMS = [
  { href: "/", label: "首页", icon: Home },
  { href: "/strategies", label: "策略实验室", icon: FlaskConical },
  { href: "/backtests", label: "回测", icon: LineChart },
  { href: "/universes", label: "标的池", icon: Layers },
  { href: "/experiments", label: "实验", icon: Beaker },
  { href: "/paper", label: "模拟交易", icon: Newspaper },
  { href: "/live", label: "实盘", icon: Workflow },
  { href: "/risk", label: "风控", icon: Shield },
  { href: "/reports", label: "报告", icon: FileBarChart2 },
  { href: "/settings", label: "设置", icon: Settings },
] as const;
