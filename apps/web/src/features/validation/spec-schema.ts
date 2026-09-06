import { z } from "zod";
import type { ValidationKind } from "@/lib/api";
import { tr } from "@/lib/translate";

export const KIND_OPTIONS: {
  value: ValidationKind;
  label: string;
  description: string;
}[] = [
  {
    value: "walk_forward",
    label: tr("validation.kindOptions.walk_forward.label"),
    description: tr("validation.kindOptions.walk_forward.description"),
  },
  {
    value: "dsr",
    label: tr("validation.kindOptions.dsr.label"),
    description: tr("validation.kindOptions.dsr.description"),
  },
  {
    value: "pbo",
    label: tr("validation.kindOptions.pbo.label"),
    description: tr("validation.kindOptions.pbo.description"),
  },
  {
    value: "sensitivity",
    label: tr("validation.kindOptions.sensitivity.label"),
    description: tr("validation.kindOptions.sensitivity.description"),
  },
  {
    value: "cost",
    label: tr("validation.kindOptions.cost.label"),
    description: tr("validation.kindOptions.cost.description"),
  },
  {
    value: "bootstrap",
    label: tr("validation.kindOptions.bootstrap.label"),
    description: tr("validation.kindOptions.bootstrap.description"),
  },
  {
    value: "regime",
    label: tr("validation.kindOptions.regime.label"),
    description: tr("validation.kindOptions.regime.description"),
  },
  {
    value: "spa",
    label: tr("validation.kindOptions.spa.label"),
    description: tr("validation.kindOptions.spa.description"),
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
