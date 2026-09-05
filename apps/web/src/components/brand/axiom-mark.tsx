import { cn } from "@/lib/utils";

/** A rising street cut through an A. Deliberately monochrome at every size. */
export function AxiomMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
      className={cn("h-8 w-8", className)}
    >
      <path
        d="M7 31 18.3 8h4L34 31h-6.2L20.2 15 12.9 31H7Z"
        fill="currentColor"
      />
      <path
        d="m14.3 25.5 14-5.8 2.2 4.5-18.8 7.7 2.6-6.4Z"
        fill="currentColor"
      />
      <path d="m13.9 24.3 13.2-5.5 1 2.1-15.6 6.5 1.4-3.1Z" fill="white" />
    </svg>
  );
}
