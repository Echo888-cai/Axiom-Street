export function PanelSectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[11px] font-semibold uppercase tracking-[.12em] text-as-muted">
      {children}
    </h2>
  );
}
