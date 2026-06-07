import { Link } from "react-router-dom";

interface AppTopBarProps {
  title?: string;
  subtitle?: string;
  actionLabel?: string;
  actionTo?: string;
}

export function AppTopBar({
  title,
  subtitle,
  actionLabel,
  actionTo,
}: AppTopBarProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          {title}
        </p>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>
      {actionTo && actionLabel ? (
        <Link
          to={actionTo}
          className="inline-flex items-center justify-center rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted transition-colors"
        >
          {actionLabel}
        </Link>
      ) : (
        <div />
      )}
    </div>
  );
}
