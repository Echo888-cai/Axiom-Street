import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Briefcase,
  ChartCandlestick,
  FlaskConical,
  History,
  Play,
  Plus,
  Sparkles,
  SquareTerminal,
  Workflow,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { useApp } from "@/store/app";
import { STRATEGIES } from "@/mocks/strategies";
import { SYMBOLS } from "@/mocks/market";

interface Item {
  id: string;
  label: string;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
  run: () => void;
}

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen, setSymbol, setStrategy, toggleCopilot, pushToast } =
    useApp();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(!useApp.getState().paletteOpen);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setPaletteOpen]);

  useEffect(() => {
    if (paletteOpen) {
      setQuery("");
      setCursor(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [paletteOpen]);

  const groups = useMemo(() => {
    const close = () => setPaletteOpen(false);
    const actions: Item[] = [
      {
        id: "run-backtest",
        label: "Run backtest",
        hint: "⌘R",
        icon: Play,
        run: () => {
          close();
          pushToast("Backtest queued", "Momentum Alpha v18 · snap_3f9a2c41");
        },
      },
      {
        id: "create-strategy",
        label: "Create strategy",
        icon: Plus,
        run: () => {
          close();
          navigate("/strategies");
          pushToast("Draft created", "Untitled strategy · DRAFT");
        },
      },
      {
        id: "ask-axiom",
        label: "Ask Axiom Copilot",
        hint: "AI",
        icon: Sparkles,
        run: () => {
          close();
          if (!useApp.getState().copilotOpen) toggleCopilot();
        },
      },
    ];
    const strategies: Item[] = STRATEGIES.map((s) => ({
      id: `strat-${s.id}`,
      label: s.name,
      hint: s.currentVersion,
      icon: Workflow,
      run: () => {
        setStrategy(s.id, s.currentVersion);
        close();
        navigate(`/strategies/${s.id}`);
      },
    }));
    const symbols: Item[] = SYMBOLS.map((s) => ({
      id: `sym-${s.symbol}`,
      label: s.symbol,
      hint: s.name,
      icon: ChartCandlestick,
      run: () => {
        setSymbol(s.symbol);
        close();
        navigate("/market");
      },
    }));
    const pages: Item[] = [
      { id: "go-research", label: "Go to Research", icon: SquareTerminal, run: () => { close(); navigate("/"); } },
      { id: "go-backtests", label: "Go to Backtests", icon: History, run: () => { close(); navigate("/backtests"); } },
      { id: "go-experiments", label: "Go to Experiments", icon: FlaskConical, run: () => { close(); navigate("/experiments"); } },
      { id: "go-portfolio", label: "Go to Portfolio", icon: Briefcase, run: () => { close(); navigate("/portfolio"); } },
    ];
    return [
      { label: "Actions", items: actions },
      { label: "Strategies", items: strategies },
      { label: "Symbols", items: symbols },
      { label: "Navigate", items: pages },
    ];
  }, [navigate, setPaletteOpen, setStrategy, setSymbol, toggleCopilot, pushToast]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return groups;
    return groups
      .map((g) => ({
        ...g,
        items: g.items.filter(
          (i) => i.label.toLowerCase().includes(q) || i.hint?.toLowerCase().includes(q),
        ),
      }))
      .filter((g) => g.items.length > 0);
  }, [groups, query]);

  const flat = filtered.flatMap((g) => g.items);

  useEffect(() => setCursor(0), [query]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, flat.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      flat[cursor]?.run();
    } else if (e.key === "Escape") {
      setPaletteOpen(false);
    }
  }

  let runningIndex = -1;

  return (
    <AnimatePresence>
      {paletteOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[2px]"
          onClick={() => setPaletteOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.98, y: -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: -6 }}
            transition={{ duration: 0.18, ease: [0.25, 1, 0.5, 1] }}
            className="mx-auto mt-[16vh] w-full max-w-[540px] overflow-hidden rounded-lg border border-edge-strong bg-panel shadow-[0_24px_70px_rgba(0,0,0,0.6)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2.5 border-b border-edge px-3.5">
              <SquareTerminal className="h-4 w-4 text-text-3" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Type a command or search…"
                className="h-11 min-w-0 flex-1 bg-transparent text-[13.5px] text-text outline-none placeholder:text-text-4"
              />
              <kbd className="mono rounded border border-edge bg-sunken px-1.5 py-0.5 text-[10px] text-text-4">
                ESC
              </kbd>
            </div>
            <div className="max-h-[340px] overflow-y-auto p-1.5">
              {filtered.length === 0 && (
                <div className="px-3 py-6 text-center text-xs text-text-3">
                  No results for “{query}”
                </div>
              )}
              {filtered.map((group) => (
                <div key={group.label}>
                  <div className="px-2.5 pt-2 pb-1 text-[10px] font-medium tracking-wider text-text-4 uppercase">
                    {group.label}
                  </div>
                  {group.items.map((item) => {
                    runningIndex++;
                    const idx = runningIndex;
                    const active = idx === cursor;
                    return (
                      <button
                        key={item.id}
                        onMouseEnter={() => setCursor(idx)}
                        onClick={item.run}
                        className={cn(
                          "interactive flex h-8 w-full cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-left text-[13px]",
                          active ? "bg-raised text-text" : "text-text-2",
                        )}
                      >
                        <item.icon
                          className={cn("h-3.5 w-3.5", active ? "text-accent" : "text-text-4")}
                        />
                        <span className="flex-1">{item.label}</span>
                        {item.hint && (
                          <span className="mono text-[10.5px] text-text-4">{item.hint}</span>
                        )}
                        {active && <ArrowRight className="h-3 w-3 text-text-4" />}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
            <div className="flex items-center gap-3 border-t border-edge px-3.5 py-1.5 text-[10px] text-text-4">
              <span className="flex items-center gap-1">
                <kbd className="mono rounded border border-edge px-1">↑↓</kbd> navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="mono rounded border border-edge px-1">↵</kbd> select
              </span>
              <span className="ml-auto">Axiom Street</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
