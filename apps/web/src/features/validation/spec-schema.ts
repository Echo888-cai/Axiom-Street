import { z } from "zod";
import type { ValidationKind } from "@/lib/api";

export const KIND_OPTIONS: {
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

export function buildZodSchema(
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
