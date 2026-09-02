"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Layers } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { toast } from "@/components/ui/toast";
import { formatRelative } from "@/lib/utils";

export function UniverseList() {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["universes"],
    queryFn: api.listUniverses,
  });

  const create = useMutation({
    mutationFn: () => api.createUniverse({ name: name.trim() }),
    onSuccess: (universe) => {
      qc.invalidateQueries({ queryKey: ["universes"] });
      toast("标的池已创建", "ok");
      setName("");
      router.push(`/universes/${universe.id}`);
    },
    onError: (err: Error) => toast(err.message, "err"),
  });

  return (
    <div className="space-y-6 as-enter">
      <PageHeader
        title="标的池"
        description="时点正确的成分列表。退市标的必须写 effective_to，否则回测会系统性偏高。"
        action={
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) create.mutate();
            }}
          >
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：含退市的美股池"
              className="w-56"
            />
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? "创建中…" : "新建标的池"}
            </Button>
          </form>
        }
      />

      {isLoading ? (
        <Card className="h-40 animate-pulse bg-as-secondary" />
      ) : error ? (
        <Card>
          <EmptyState title="API 未连接" description="请先启动 FastAPI 服务（端口 8000）。" />
        </Card>
      ) : !data?.length ? (
        <Card className="min-h-[320px]">
          <EmptyState
            icon={Layers}
            title="还没有标的池"
            description="回测目前会默认使用快照里的全部标的，无法表达退市。建一个池，给每支股票写上有效区间。"
          />
        </Card>
      ) : (
        <div className="grid gap-3 as-stagger">
          {data.map((item) => (
            <Link key={item.id} href={`/universes/${item.id}`}>
              <Card hover className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-medium text-as-text">{item.name}</div>
                    <Badge tone="blue">{item.kind}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-as-muted">
                    {item.description || "暂无描述"}
                  </div>
                </div>
                <div className="shrink-0 text-right text-xs text-as-muted">
                  <div className="tabular-nums text-sm text-as-text">{item.member_count} 支</div>
                  <div>{formatRelative(item.updated_at)}</div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
