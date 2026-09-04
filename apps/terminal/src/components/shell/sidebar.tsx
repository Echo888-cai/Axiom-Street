import {
  Briefcase,
  ChartCandlestick,
  CirclePlay,
  Database,
  FlaskConical,
  History,
  Lightbulb,
  Radio,
  Search,
  Settings,
  SquareTerminal,
  Workflow,
} from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { cn } from "@/lib/cn";
import { useApp } from "@/store/app";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    label: "Research",
    items: [
      { to: "/", label: "Overview", icon: SquareTerminal },
      { to: "/market", label: "Market", icon: ChartCandlestick },
      { to: "/ideas", label: "Ideas", icon: Lightbulb },
    ],
  },
  {
    label: "Strategies",
    items: [
      { to: "/strategies", label: "My Strategies", icon: Workflow },
      { to: "/experiments", label: "Experiments", icon: FlaskConical },
    ],
  },
  {
    label: "Trading",
    items: [
      { to: "/backtests", label: "Backtests", icon: History },
      { to: "/paper", label: "Paper Trading", icon: CirclePlay },
      { to: "/live", label: "Live Trading", icon: Radio },
    ],
  },
  {
    label: "Portfolio",
    items: [{ to: "/portfolio", label: "Portfolio", icon: Briefcase }],
  },
  {
    label: "Data",
    items: [{ to: "/data", label: "Data", icon: Database }],
  },
];

export function Sidebar() {
  const setPaletteOpen = useApp((s) => s.setPaletteOpen);
  const navigate = useNavigate();

  return (
    <aside className="flex w-[228px] shrink-0 flex-col border-r border-edge bg-sunken">
      {/* Logo */}
      <div className="flex h-12 items-center gap-2.5 border-b border-edge px-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-md bg-[#f4f4f2]">
          <img
            src="/logo.png"
            alt="Axiom Street"
            width={32}
            height={32}
            className="h-7 w-7 object-contain"
          />
        </div>
        <span className="truncate text-[13px] font-semibold tracking-tight text-text">
          Axiom Street
        </span>
      </div>

      {/* Search trigger */}
      <div className="px-2.5 pt-2.5">
        <button
          onClick={() => setPaletteOpen(true)}
          className="interactive flex h-7 w-full cursor-pointer items-center gap-2 rounded-md border border-edge bg-panel px-2 text-text-3 hover:border-edge-strong hover:text-text-2"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="flex-1 text-left text-xs">Search</span>
          <kbd className="mono rounded border border-edge bg-sunken px-1 text-[10px] text-text-3">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Nav */}
      <nav className="min-h-0 flex-1 overflow-y-auto px-2.5 py-3">
        {NAV.map((group) => (
          <div key={group.label} className="mb-4">
            <div className="px-2 pb-1.5 text-[10.5px] font-medium tracking-wider text-text-4 uppercase">
              {group.label}
            </div>
            <ul className="space-y-px">
              {group.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      cn(
                        "interactive group relative flex h-7 items-center gap-2 rounded-md px-2 text-[13px]",
                        isActive
                          ? "bg-raised/70 text-text"
                          : "text-text-3 hover:bg-raised/40 hover:text-text-2",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span
                          className={cn(
                            "absolute top-1/2 left-0 h-3.5 w-[2px] -translate-y-1/2 rounded-full transition-colors duration-200",
                            isActive ? "bg-accent" : "bg-transparent",
                          )}
                        />
                        <item.icon
                          className={cn(
                            "h-3.5 w-3.5 shrink-0",
                            isActive ? "text-text-2" : "text-text-4 group-hover:text-text-3",
                          )}
                        />
                        {item.label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-edge p-2.5">
        <button
          onClick={() => navigate("/settings")}
          className="interactive flex h-7 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-[13px] text-text-3 hover:bg-raised/40 hover:text-text-2"
        >
          <Settings className="h-3.5 w-3.5 text-text-4" />
          Settings
        </button>
        <div className="mt-1 flex items-center gap-2 rounded-md px-2 py-1.5">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-raised text-[10px] font-semibold text-text-2">
            AR
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs text-text-2">Arlan Research</div>
            <div className="mono truncate text-[10px] text-text-4">acct 0x7f…c2</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
