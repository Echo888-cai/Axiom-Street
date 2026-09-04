import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { useApp } from "@/store/app";
import { getStrategy, getVersion } from "@/mocks/strategies";
import { getVersionData } from "@/mocks/engine";
import {
  askCopilot,
  SUGGESTED_PROMPTS,
  type CopilotContext,
  type CopilotReply,
} from "@/mocks/copilot";
import { IconButton } from "@/components/ui/button";

interface Msg {
  id: number;
  role: "user" | "axiom";
  text: string;
  reply?: CopilotReply;
  pending?: boolean;
}

let msgId = 0;

export function Copilot() {
  const navigate = useNavigate();
  const { symbol, strategyId, version, range, toggleCopilot, pushToast } = useApp();
  const strategy = getStrategy(strategyId);
  const v = getVersion(strategy, version);
  const metrics = getVersionData(v).metrics;

  const ctx: CopilotContext = {
    page: "research",
    symbol,
    strategyName: strategy.name,
    version: v.version,
    range,
    metrics,
  };

  const [messages, setMessages] = useState<Msg[]>([
    {
      id: msgId++,
      role: "axiom",
      text: "",
      reply: {
        summary: `Watching ${strategy.name} ${v.version} against ${strategy.benchmark}. Sharpe ${metrics.sharpe.toFixed(2)}, max drawdown ${(metrics.maxDrawdown * 100).toFixed(1)}%, 41 trials logged on this snapshot. Ask me anything about this research context.`,
        actions: [],
      },
    },
  ]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function ask(question: string) {
    if (!question.trim()) return;
    setInput("");
    const userMsg: Msg = { id: msgId++, role: "user", text: question };
    const pendingMsg: Msg = { id: msgId++, role: "axiom", text: "", pending: true };
    setMessages((m) => [...m, userMsg, pendingMsg]);
    setTimeout(() => {
      const reply = askCopilot(question, ctx);
      setMessages((m) =>
        m.map((msg) => (msg.id === pendingMsg.id ? { ...msg, reply, pending: false } : msg)),
      );
    }, 700);
  }

  function runAction(actionId: string, label: string) {
    switch (actionId) {
      case "compare-versions":
      case "compare-2021-2022":
        navigate("/experiments");
        pushToast("Comparison opened", "v14 → v18 overlay in Experiments");
        break;
      case "run-experiment":
        pushToast("Experiment queued", "Walk-forward · 12 folds · anchored start");
        break;
      case "adjust-params":
        navigate(`/strategies/${strategyId}`);
        pushToast("Parameter panel", `Editing ${strategy.name} ${v.version}`);
        break;
      case "open-portfolio":
        navigate("/portfolio");
        break;
      case "open-validation":
        navigate("/experiments");
        pushToast("Validation desk", "Deflated Sharpe · PBO · cost sensitivity");
        break;
      case "analyze-regime":
        ask("Decompose returns by macro regime");
        break;
      default:
        if (actionId.startsWith("q-")) ask(label);
        else pushToast(label, "Action acknowledged by Copilot");
    }
  }

  return (
    <motion.aside
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 324, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.22, ease: [0.25, 1, 0.5, 1] }}
      className="flex h-full shrink-0 flex-col overflow-hidden border-l border-edge bg-sunken"
    >
      {/* Header */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-edge px-3">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-accent" />
          <span className="text-[13px] font-medium text-text">Axiom Copilot</span>
        </div>
        <IconButton onClick={toggleCopilot} title="Close Copilot">
          <X className="h-3.5 w-3.5" />
        </IconButton>
      </div>

      {/* Context chips */}
      <div className="flex shrink-0 flex-wrap items-center gap-1 border-b border-edge px-3 py-2">
        <ContextChip label={strategy.name} />
        <ContextChip label={v.version} accent />
        <ContextChip label={symbol} />
        <ContextChip label={range} />
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-3">
        {messages.map((msg) =>
          msg.role === "user" ? (
            <div key={msg.id} className="flex justify-end">
              <div className="max-w-[92%] rounded-md rounded-br-sm border border-edge bg-raised px-2.5 py-1.5 text-[12.5px] text-text">
                {msg.text}
              </div>
            </div>
          ) : (
            <div key={msg.id} className="space-y-2">
              {msg.pending ? (
                <div className="flex items-center gap-1.5 px-0.5 py-1">
                  <span className="skeleton h-2 w-2 rounded-full" />
                  <span className="skeleton h-2 w-2 rounded-full [animation-delay:150ms]" />
                  <span className="skeleton h-2 w-2 rounded-full [animation-delay:300ms]" />
                </div>
              ) : msg.reply ? (
                <AxiomReply reply={msg.reply} onAction={runAction} />
              ) : null}
            </div>
          ),
        )}
      </div>

      {/* Suggested prompts */}
      {messages.length <= 1 && (
        <div className="shrink-0 space-y-1 px-3 pb-2">
          {SUGGESTED_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => ask(p)}
              className="interactive flex w-full cursor-pointer items-center justify-between rounded-md border border-edge px-2.5 py-1.5 text-left text-xs text-text-2 hover:border-edge-strong hover:bg-raised/50 hover:text-text"
            >
              {p}
              <ArrowRight className="h-3 w-3 text-text-4" />
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <form
        className="shrink-0 border-t border-edge p-2.5"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <div className="flex items-center gap-2 rounded-md border border-edge bg-panel px-2.5 focus-within:border-edge-strong">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about this research context…"
            className="h-8 min-w-0 flex-1 bg-transparent text-[12.5px] text-text outline-none placeholder:text-text-4"
          />
          <kbd className="mono shrink-0 rounded border border-edge bg-sunken px-1 text-[9.5px] text-text-4">
            ↵
          </kbd>
        </div>
      </form>
    </motion.aside>
  );
}

function ContextChip({ label, accent }: { label: string; accent?: boolean }) {
  return (
    <span
      className={cn(
        "mono rounded border px-1.5 py-0.5 text-[10px]",
        accent
          ? "border-accent/25 bg-accent-dim text-accent"
          : "border-edge bg-panel text-text-3",
      )}
    >
      {label}
    </span>
  );
}

function AxiomReply({
  reply,
  onAction,
}: {
  reply: CopilotReply;
  onAction: (id: string, label: string) => void;
}) {
  return (
    <div className="space-y-2.5 text-[12.5px] leading-relaxed">
      <p className="text-text-2">{reply.summary}</p>

      {reply.drivers && (
        <div className="space-y-1.5">
          {reply.drivers.map((d) => (
            <div key={d.n} className="group rounded-md border border-edge bg-panel px-2.5 py-2">
              <div className="flex items-baseline gap-2">
                <span className="mono text-[10px] font-medium text-accent">{d.n}</span>
                <span className="text-xs font-medium text-text">{d.title}</span>
              </div>
              <p className="mt-1 pl-5 text-[11.5px] leading-snug text-text-3">{d.detail}</p>
            </div>
          ))}
        </div>
      )}

      {reply.callout && (
        <div
          className={cn(
            "rounded-md border px-2.5 py-2 text-[11.5px] leading-snug",
            reply.callout.tone === "warn"
              ? "border-accent/25 bg-accent-dim/60 text-[#d9c48f]"
              : "border-edge bg-panel text-text-3",
          )}
        >
          {reply.callout.text}
        </div>
      )}

      {reply.actions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {reply.actions.map((a) => (
            <button
              key={a.id}
              onClick={() => onAction(a.id, a.label)}
              title={a.hint}
              className="interactive pressable cursor-pointer rounded-md border border-edge-strong px-2 py-1 text-[11px] text-text-2 hover:border-accent/40 hover:bg-accent-dim hover:text-accent"
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
