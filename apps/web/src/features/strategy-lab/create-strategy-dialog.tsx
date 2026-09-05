"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, FlaskConical, Layers, X, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { EQUAL_WEIGHT_CONFIG, EQUAL_WEIGHT_TEMPLATE } from "@/lib/equal-weight";
import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "@/components/ui/toast";

export function CreateStrategyDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [template, setTemplate] = useState("trend");
  const [name, setName] = useState("");
  const router = useRouter();
  const qc = useQueryClient();
  const create = useMutation({
    mutationFn: () =>
      api.createStrategy({
        name:
          name.trim() ||
          (template === "trend" ? "SPY 200日均线" : "等权横截面策略"),
        description:
          template === "trend"
            ? "价格站上 200 日均线持有 SPY，跌破则空仓。"
            : "在标的池内按等权配置，定期再平衡。",
        ...(template === "equal"
          ? { code: EQUAL_WEIGHT_TEMPLATE, config: EQUAL_WEIGHT_CONFIG }
          : {}),
      }),
    onSuccess: (strategy) => {
      qc.invalidateQueries({ queryKey: ["strategies"] });
      toast("研究已创建", "ok");
      onClose();
      router.push(`/strategies/${strategy.id}`);
    },
  });
  return (
    <Modal open={open} onClose={onClose} label="新建研究">
      <form
        className="p-6 sm:p-8"
        onSubmit={(event) => {
          event.preventDefault();
          if (!create.isPending) create.mutate();
        }}
      >
        <div className="flex items-start justify-between">
          <span className="as-icon-well h-12 w-12 rounded-2xl">
            <FlaskConical className="h-5 w-5" strokeWidth={1.5} />
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClose}
            aria-label="关闭新建研究"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        <h2 className="mt-6 text-2xl font-semibold tracking-tight">
          开始一项新研究
        </h2>
        <p className="mt-2 text-xs leading-6 text-as-muted">
          选择一个起点，然后写下属于你的假设。
        </p>
        <label
          htmlFor="research-name"
          className="mb-2 mt-6 block text-xs font-medium"
        >
          研究名称
        </label>
        <Input
          id="research-name"
          autoFocus
          className="w-full"
          maxLength={200}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={
            template === "trend" ? "SPY 200日均线" : "等权横截面策略"
          }
        />
        <fieldset className="mt-6">
          <legend className="mb-3 text-xs font-medium">选择策略模板</legend>
          <div className="space-y-2">
            {[
              {
                id: "trend",
                title: "趋势跟踪",
                description: "SPY · 200 日均线 · 单标的",
                icon: FlaskConical,
              },
              {
                id: "equal",
                title: "等权配置",
                description: "多标的 · 1/N 权重 · 定期再平衡",
                icon: Layers,
              },
            ].map((item) => (
              <label
                key={item.id}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-2xl border p-4 transition-colors",
                  template === item.id
                    ? "border-as-primary/30 bg-as-primary/5"
                    : "border-as-border bg-white/70 hover:bg-white",
                )}
              >
                <input
                  type="radio"
                  name="template"
                  value={item.id}
                  checked={template === item.id}
                  onChange={() => setTemplate(item.id)}
                  className="sr-only peer"
                />
                <item.icon
                  className="h-5 w-5 text-as-muted"
                  strokeWidth={1.5}
                />
                <span className="flex-1 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-as-primary">
                  <span className="block text-xs font-medium">
                    {item.title}
                  </span>
                  <span className="mt-1.5 block text-[11px] text-as-muted">
                    {item.description}
                  </span>
                </span>
                {template === item.id && (
                  <Check className="h-4 w-4 text-as-primary" />
                )}
              </label>
            ))}
          </div>
        </fieldset>
        {create.isError && (
          <p
            role="alert"
            className="mt-4 rounded-xl bg-as-negative/5 p-3 text-xs text-as-negative"
          >
            {create.error.message}
          </p>
        )}
        <div className="mt-7 flex justify-end gap-2 border-t border-as-border pt-5">
          <Button type="button" variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "正在创建…" : "创建并开始研究"}
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </form>
    </Modal>
  );
}
