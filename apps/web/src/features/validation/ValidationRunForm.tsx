"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { KIND_OPTIONS, buildZodSchema } from "./spec-schema";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Disclosure } from "@/components/ui/disclosure";
import { useT, useI18n } from "@/lib/i18n";
import { request } from "@/lib/api/http";
import type { ValidationSpec, ValidationRun } from "@/lib/api";

interface ValidationRunFormProps {
  spec: ValidationSpec;
  strategyVersionId: string;
  backtestId?: string;
  onSubmit?: (data: unknown) => Promise<void>;
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
        message: err instanceof Error ? err.message : t("validation.form.error"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const kindOption = KIND_OPTIONS.find((k) => k.value === spec.kind);

  return (
    <Card className="w-full border-0 p-0 shadow-none sm:p-0">
      <CardHeader
        title={kindOption?.label || spec.display_name}
        hint={
          <Disclosure title="方法说明" className="mt-2">
            {kindOption?.description || spec.description}
          </Disclosure>
        }
      />
      <CardContent>
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
          <Disclosure title="运行须知与数据版本">
            <p className="mb-4 text-xs">
              {i18n.validation.form.helpText?.[
                spec.kind as keyof typeof i18n.validation.form.helpText
              ] || ""}
            </p>

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
          </Disclosure>

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
                      <option value="true">{t("validation.form.yes")}</option>
                      <option value="false">{t("validation.form.no")}</option>
                    </Select>
                  ) : type === "array" ? (
                    <Textarea
                      {...form.register(key)}
                      placeholder={t("validation.form.jsonArrayPlaceholder")}
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

