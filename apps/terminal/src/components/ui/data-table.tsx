import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface Column<T> {
  key: string;
  header: ReactNode;
  align?: "left" | "right" | "center";
  width?: string;
  mono?: boolean;
  render: (row: T, index: number) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  dense?: boolean;
  className?: string;
  maxHeight?: string;
}

/**
 * Dense, quiet data grid. Mono figures right-aligned, hairline rows,
 * hover reveals — never striped, never boxed.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  dense,
  className,
  maxHeight,
}: DataTableProps<T>) {
  return (
    <div className={cn("min-h-0 overflow-auto", className)} style={{ maxHeight }}>
      <table className="w-full border-collapse">
        <thead className="sticky top-0 z-10 bg-panel">
          <tr className="border-b border-edge">
            {columns.map((col) => (
              <th
                key={col.key}
                style={{ width: col.width }}
                className={cn(
                  "px-3 py-2 text-[10.5px] font-medium tracking-wide text-text-3 uppercase",
                  col.align === "right" && "text-right",
                  col.align === "center" && "text-center",
                  (!col.align || col.align === "left") && "text-left",
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                "interactive border-b border-edge/60 last:border-0",
                onRowClick && "cursor-pointer hover:bg-raised/50",
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    "px-3 text-[12.5px] text-text-2",
                    dense ? "py-1.5" : "py-2.5",
                    col.mono && "mono tnum",
                    col.align === "right" && "text-right",
                    col.align === "center" && "text-center",
                  )}
                >
                  <Fragment key={col.key}>{col.render(row, i)}</Fragment>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
