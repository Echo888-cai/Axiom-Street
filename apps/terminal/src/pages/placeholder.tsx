import { PanelRight } from "lucide-react";
import { useApp } from "@/store/app";
import { ContextActions, ContextBar, ContextDivider, HonestyMarker } from "@/components/shell/context-bar";
import { IconButton } from "@/components/ui/button";

/**
 * Honest placeholder — no fake charts, no lorem ipsum.
 * The demo slice ships Research / Strategy / Backtest at full depth;
 * everything else declares itself instead of pretending.
 */
export function PlaceholderPage({
  title,
  note,
  icon: Icon,
}: {
  title: string;
  note: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const toggleCopilot = useApp((s) => s.toggleCopilot);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ContextBar>
        <h1 className="text-[13.5px] font-semibold text-text">{title}</h1>
        <ContextDivider />
        <span className="mono text-[10.5px] text-text-3">not in this demo slice</span>
        <ContextActions>
          <HonestyMarker />
          <IconButton onClick={toggleCopilot} title="Toggle Copilot">
            <PanelRight className="h-3.5 w-3.5" />
          </IconButton>
        </ContextActions>
      </ContextBar>
      <div className="flex flex-1 items-center justify-center">
        <div className="flex max-w-[320px] flex-col items-center text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-edge bg-panel">
            <Icon className="h-4.5 w-4.5 text-text-3" />
          </div>
          <h2 className="mt-3 text-[13.5px] font-medium text-text">{title}</h2>
          <p className="mt-1.5 text-xs leading-relaxed text-text-3">{note}</p>
        </div>
      </div>
    </div>
  );
}
