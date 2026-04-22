interface StatusPillProps {
  tone: "ready" | "warn" | "danger" | "neutral";
  label: string;
}

export function StatusPill({ tone, label }: StatusPillProps) {
  return <span className={`status-pill status-pill--${tone}`}>{label}</span>;
}

