"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { useT, useI18n } from "@/lib/i18n";
import { request } from "@/lib/api/http";
import type { ValidationKind, ValidationSpec, ValidationRun } from "@/lib/api";

interface ValidationRunFormProps {
  spec: ValidationSpec;
  strategyVersionId: string;
  backtestId?: string;
  onSubmit?: (data: unknown) => Promise<void>;
}

const KIND_OPTIONS: {
  value: ValidationKind;
  label: string;
  description: string;
}[] = [
  {
    value: "walk_forward",
    label: "Walk-Forward",
    description: "滚动训练/测试折叠，评分用拼接样本外 Sharpe",
  },
  {
    value: "dsr",
    label: "Deflated Sharpe Ratio",
    description: "基于试验台账的多重检验与非正态修正",
  },
  {
    value: "pbo",
    label: "PBO (过拟合概率)",
    description: "组合对称交叉验证 (CSCV)",
  },
  {
    value: "sensitivity",
    label: "参数敏感性",
    description: "参数网格扰动，判定高原 vs 孤峰",
  },
  {
    value: "cost",
    label: "成本敏感性",
    description: "单边成本全计入滑点，求盈亏平衡点",
  },
  {
    value: "bootstrap",
    label: "Stationary Bootstrap CI",
    description: "保留自相关结构的置信区间",
  },
  {
    value: "regime",
    label: "制度稳定性",
    description: "牛/熊、波动、利率周期切分",
  },
  {
    value: "spa",
    label: "Hansen SPA",
    description: "试验台账上的多重检验校正",
  },
];

function buildZodType(
  type: string,
  prop: Record<string, unknown>,
): z.ZodTypeAny {
  let field: z.ZodTypeAny;

  switch (type) {
    case "string": {
      let strField = z.string();
      if (prop.format === "date") strField = strField.date();
      if (prop.pattern)
        strField = strField.regex(new RegExp(prop.pattern as string));
      if (prop.minLength) strField = strField.min(prop.minLength as number);
      if (prop.maxLength) strField = strField.max(prop.maxLength as number);
      if (prop.enum) {
        return z.enum(prop.enum as [string, ...string[]]);
      }
      field = strField;
      break;
    }
    case "number":
    case "integer": {
      let numField = type === "integer" ? z.number().int() : z.number();
      if (prop.minimum !== undefined)
        numField = numField.min(prop.minimum as number);
      if (prop.maximum !== undefined)
        numField = numField.max(prop.maximum as number);
      if (prop.exclusiveMinimum !== undefined)
        numField = numField.gt(prop.exclusiveMinimum as number);
      if (prop.exclusiveMaximum !== undefined)
        numField = numField.lt(prop.exclusiveMaximum as number);
      if (prop.multipleOf !== undefined)
        numField = numField.multipleOf(prop.multipleOf as number);
      field = numField;
      break;
    }
    case "boolean":
      return z.boolean();
    case "array": {
      const itemsProp = prop.items as { type?: string } | undefined;
      const items = itemsProp
        ? buildZodType(
            itemsProp.type as string,
            itemsProp as Record<string, unknown>,
          )
        : z.unknown();
      return z.array(items);
    }
    default:
      return z.unknown();
  }
  return field;
}

function buildZodSchema(
  schema: Record<string, unknown>,
): z.ZodObject<Record<string, z.ZodTypeAny>> {
  const shape: Record<string, z.ZodTypeAny> = {};

  const props =
    (schema.properties as Record<string, Record<string, unknown>>) || {};
  const required = (schema.required as string[]) || [];

  for (const [key, prop] of Object.entries(props)) {
    const p = prop;
    const isRequired = required.includes(key);

    const type = p.type as string | string[];
    let field: z.ZodTypeAny;

    if (Array.isArray(type)) {
      const unionTypes = type.map((t) => buildZodType(t as string, p));
      field = z
        .union(unionTypes as [z.ZodTypeAny, z.ZodTypeAny, ...z.ZodTypeAny[]])
        .optional();
    } else if (p.enum) {
      field = z.enum(p.enum as [string, ...string[]]);
    } else {
      field = buildZodType(type as string, p);
    }

    if (p.default !== undefined && !isRequired) {
      field = field.default(p.default);
    }

    if (!isRequired) {
      field = field.optional();
    }

    shape[key] = field;
  }

  return z.object(shape);
}

export function ValidationRunForm({
  spec,
  strategyVersionId,
  backtestId,
  onSubmit,
}: ValidationRunFormProps) {
  const t = useT();
  const i18n = useI18n();
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const schema = useMemo(
    () => buildZodSchema(spec.params_schema),
    [spec.params_schema],
  );

  const form = useForm<Record<string, unknown>>({
    resolver: zodResolver(schema),
    defaultValues: {},
    mode: "onChange",
  });

  const handleSubmit = async (data: Record<string, unknown>) => {
    setIsSubmitting(true);
    try {
      const payload = {
        kind: spec.kind,
        strategy_version_id: strategyVersionId,
        backtest_id: backtestId || null,
        params: data,
      };

      if (onSubmit) {
        await onSubmit(payload);
      } else {
        await request<ValidationRun>("/api/v1/validation", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        router.push("/validation");
      }
    } catch (err) {
      form.setError("root", {
        message: err instanceof Error ? err.message : "提交失败",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const kindOption = KIND_OPTIONS.find((k) => k.value === spec.kind);

  return (
    <Card className="w-full max-w-3xl">
      <CardHeader
        title={kindOption?.label || spec.display_name}
        hint={
          <p className="text-sm text-muted-foreground mt-1">
            {kindOption?.description || spec.description}
          </p>
        }
      />
      <CardContent>
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
          <Alert className="border-primary/20 bg-primary/5">
            <AlertDescription className="text-sm">
              {i18n.validation.form.helpText?.[
                spec.kind as keyof typeof i18n.validation.form.helpText
              ] || ""}
            </AlertDescription>
          </Alert>

          <Separator />

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="strategy_version_id">
                {i18n.validation.form.strategyVersionIdLabel}
              </Label>
              <Input
                id="strategy_version_id"
                value={strategyVersionId}
                disabled
                className="mt-1"
              />
            </div>
            {backtestId && (
              <div className="sm:col-span-2">
                <Label htmlFor="backtest_id">
                  {i18n.validation.form.backtestIdLabel}
                </Label>
                <Input
                  id="backtest_id"
                  value={backtestId}
                  disabled
                  className="mt-1"
                />
              </div>
            )}
          </div>

          <div className="space-y-4">
            {Object.entries(
              (spec.params_schema.properties as Record<
                string,
                {
                  type?: string;
                  title?: string;
                  description?: string;
                  enum?: string[];
                  default?: unknown;
                  minimum?: number;
                  maximum?: number;
                  format?: string;
                  pattern?: string;
                  items?: { type: string };
                }
              >) || {},
            ).map(([key, prop]) => {
              const p = prop;
              const required = (
                (spec.params_schema.required as string[]) || []
              ).includes(key);
              const isEnum = !!p.enum;
              const type = p.type as string;

              return (
                <div key={key} className="space-y-1.5">
                  <Label htmlFor={key} className="flex items-center gap-1.5">
                    {p.title || key}
                    {required && (
                      <span className="text-xs text-red-500">*</span>
                    )}
                  </Label>
                  {p.description && (
                    <p className="text-xs text-muted-foreground">
                      {p.description}
                    </p>
                  )}

                  {isEnum ? (
                    <Select
                      {...form.register(key)}
                      onChange={(e) => form.setValue(key, e.target.value)}
                    >
                      {(p.enum as string[]).map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </Select>
                  ) : type === "boolean" ? (
                    <Select
                      {...form.register(key)}
                      onChange={(e) =>
                        form.setValue(key, e.target.value === "true")
                      }
                    >
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </Select>
                  ) : type === "array" ? (
                    <Textarea
                      {...form.register(key)}
                      placeholder="JSON 数组，如 [1, 2, 3]"
                      className="font-mono text-sm min-h-[80px]"
                      onChange={(e) => {
                        try {
                          form.setValue(key, JSON.parse(e.target.value));
                        } catch {
                          form.setValue(key, e.target.value);
                        }
                      }}
                    />
                  ) : (
                    <Input
                      {...form.register(key)}
                      type={
                        type === "number" || type === "integer"
                          ? "number"
                          : "text"
                      }
                      placeholder={p.title || key}
                      step={type === "number" ? "any" : undefined}
                      min={p.minimum as number | undefined}
                      max={p.maximum as number | undefined}
                    />
                  )}

                  {form.formState.errors[key] && (
                    <p className="text-sm text-red-500" role="alert">
                      {form.formState.errors[key].message}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {form.formState.errors.root && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>
                {form.formState.errors.root.message}
              </AlertDescription>
            </Alert>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button
              type="button"
              variant="secondary"
              onClick={() => router.back()}
            >
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="min-w-[140px]"
            >
              {isSubmitting ? t("common.loading") : i18n.validation.form.submit}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export function ValidationRunFormWrapper({
  kind,
  strategyVersionId,
  backtestId,
  specs,
}: {
  kind: ValidationKind;
  strategyVersionId: string;
  backtestId?: string;
  specs: ValidationSpec[];
}) {
  const spec = specs.find((s) => s.kind === kind);
  if (!spec) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        未找到验证类型: {kind}
      </div>
    );
  }
  return (
    <ValidationRunForm
      spec={spec}
      strategyVersionId={strategyVersionId}
      backtestId={backtestId}
    />
  );
}
