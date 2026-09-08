"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { copilotApi, type CopilotResource } from "@/lib/api/copilot";
import type { CopilotChatMessage } from "@/lib/api/types";
import { useT } from "@/lib/i18n";
import { PanelSectionTitle } from "./section-title";

const POLL_MS = 2_000;
const STALE_MS = 30_000;
const MAX_AWAIT_MS = 120_000;
const MAX_MESSAGE_CHARS = 1_200;

const QUICK_PROMPTS = [
  ["quickStop", "quickStopPrompt"],
  ["quickNext", "quickNextPrompt"],
  ["quickPaper", "quickPaperPrompt"],
] as const;

function ChatRow({ row }: { row: CopilotChatMessage }) {
  const t = useT();
  return (
    <article className="space-y-2 border-b border-as-border/70 pb-3 last:border-b-0 last:pb-0">
      <p className="text-[11.5px] leading-relaxed text-as-muted">{row.user_message}</p>
      {row.status === "DONE" ? (
        <p className="whitespace-pre-line text-[12.5px] leading-relaxed text-as-text">
          {row.assistant_message}
        </p>
      ) : row.status === "FAILED" ? (
        <div className="space-y-1">
          <p className="text-[12px] font-medium text-as-negative">{t("copilot.chat.failed")}</p>
          {row.error ? (
            <p className="break-words text-[11.5px] leading-relaxed text-as-muted">{row.error}</p>
          ) : null}
        </div>
      ) : (
        <p className="text-[12px] text-as-muted">{t("copilot.chat.queued")}</p>
      )}
    </article>
  );
}

export function ChatBlock({
  resource,
  id,
  strategyId,
  providerEnabled,
  providerName,
  pollMs = POLL_MS,
}: {
  resource: CopilotResource;
  id: string;
  strategyId: string;
  providerEnabled: boolean;
  providerName: string;
  pollMs?: number;
}) {
  const t = useT();
  const [message, setMessage] = useState("");
  const [awaiting, setAwaiting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const headAtClick = useRef<string | null>(null);

  const list = useQuery({
    queryKey: ["copilot-chat", strategyId],
    queryFn: () => copilotApi.listChat(strategyId),
    refetchInterval: awaiting ? pollMs : false,
    staleTime: STALE_MS,
    enabled: providerEnabled,
  });
  const rows = list.data ?? [];
  const latest = rows[0];

  useEffect(() => {
    if (awaiting && latest && latest.id !== headAtClick.current) {
      setAwaiting(false);
    }
  }, [awaiting, latest]);

  useEffect(() => {
    if (!awaiting) return;
    const timer = window.setTimeout(() => setAwaiting(false), MAX_AWAIT_MS);
    return () => window.clearTimeout(timer);
  }, [awaiting]);

  if (!providerEnabled) {
    return (
      <section className="space-y-2">
        <PanelSectionTitle>{t("copilot.chat.title")}</PanelSectionTitle>
        <p className="rounded-xl border border-as-border bg-as-bg px-3 py-2.5 text-[12px] leading-relaxed text-as-muted">
          {t("copilot.chat.disabled")}
        </p>
        <p className="px-0.5 text-[10px] leading-snug text-as-muted">{t("copilot.chat.privacy")}</p>
      </section>
    );
  }

  async function submit(prompt = message) {
    const normalized = prompt.trim();
    if (!normalized || normalized.length > MAX_MESSAGE_CHARS || awaiting) return;
    setActionError(null);
    headAtClick.current = latest?.id ?? null;
    setAwaiting(true);
    setMessage("");
    try {
      await copilotApi.chat(resource, id, normalized);
    } catch (error) {
      setAwaiting(false);
      setMessage(normalized);
      setActionError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <PanelSectionTitle>{t("copilot.chat.title")}</PanelSectionTitle>
        {providerName ? <span className="font-mono text-[10px] text-as-muted">{providerName}</span> : null}
      </div>
      <p className="text-[10px] leading-snug text-as-muted">{t("copilot.chat.privacy")}</p>
      <div className="flex flex-wrap gap-1.5">
        {QUICK_PROMPTS.map(([labelKey, promptKey]) => (
          <Button
            key={labelKey}
            size="sm"
            variant="secondary"
            disabled={awaiting || list.isLoading}
            onClick={() => submit(t(`copilot.chat.${promptKey}`))}
          >
            {t(`copilot.chat.${labelKey}`)}
          </Button>
        ))}
      </div>
      <div className="space-y-2 rounded-xl border border-as-border bg-as-bg p-2.5">
        {list.isLoading && !latest ? (
          <p className="text-[12px] text-as-muted">{t("copilot.chat.queued")}</p>
        ) : rows.length ? (
          <div className="max-h-72 space-y-3 overflow-y-auto">
            {[...rows].reverse().map((row) => <ChatRow key={row.id} row={row} />)}
          </div>
        ) : (
          <p className="text-[12px] leading-relaxed text-as-muted">{t("copilot.chat.empty")}</p>
        )}
        {awaiting ? <p className="text-[11px] text-as-muted">{t("copilot.chat.sending")}</p> : null}
      </div>
      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <Textarea
          value={message}
          onChange={(event) => setMessage(event.target.value.slice(0, MAX_MESSAGE_CHARS))}
          placeholder={t("copilot.chat.placeholder")}
          disabled={awaiting}
          rows={3}
          aria-label={t("copilot.chat.placeholder")}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] tabular-nums text-as-muted">
            {message.length}/{MAX_MESSAGE_CHARS} {t("copilot.chat.charCount")}
          </span>
          <Button size="sm" type="submit" disabled={awaiting || !message.trim()}>
            {awaiting ? t("copilot.chat.sending") : t("copilot.chat.send")}
          </Button>
        </div>
      </form>
      {actionError ? <p className="text-[11.5px] leading-relaxed break-words text-as-negative">{actionError}</p> : null}
      {list.isError ? <p className="text-[11px] text-as-muted">{t("copilot.chat.failed")}</p> : null}
    </section>
  );
}
