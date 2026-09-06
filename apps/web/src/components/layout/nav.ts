import {
  BadgeCheck,
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
import type { ZhCN } from "@/locales";

export type NavKey = keyof ZhCN["nav"];

export const NAV_ITEMS: { href: string; key: NavKey; icon: typeof Home }[] = [
  { href: "/", key: "home", icon: Home },
  { href: "/strategies", key: "strategies", icon: FlaskConical },
  { href: "/backtests", key: "backtests", icon: LineChart },
  { href: "/validation", key: "validation", icon: BadgeCheck },
  { href: "/universes", key: "universes", icon: Layers },
  { href: "/experiments", key: "experiments", icon: Beaker },
  { href: "/paper", key: "paper", icon: Newspaper },
  { href: "/live", key: "live", icon: Workflow },
  { href: "/risk", key: "risk", icon: Shield },
  { href: "/reports", key: "reports", icon: FileBarChart2 },
  { href: "/settings", key: "settings", icon: Settings },
];
