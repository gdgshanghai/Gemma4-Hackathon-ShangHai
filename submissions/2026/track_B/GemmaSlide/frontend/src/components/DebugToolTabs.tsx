import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

const linkClasses = (isActive: boolean) =>
  cn(
    "rounded-full px-4 py-2 text-sm font-medium transition",
    isActive
      ? "bg-primary text-primary-foreground"
      : "bg-muted text-foreground hover:bg-accent",
  );

export function DebugToolTabs() {
  return (
    <Card className="mb-5">
      <CardContent className="p-3">
        <div className="flex flex-wrap gap-2">
          <NavLink
            to="/debug/parser"
            className={({ isActive }) => linkClasses(isActive)}
          >
            Parser Debug
          </NavLink>

          <NavLink
            to="/debug/jobs"
            className={({ isActive }) => linkClasses(isActive)}
          >
            Jobs Debug
          </NavLink>

          <NavLink
            to="/debug/live"
            className={({ isActive }) => linkClasses(isActive)}
          >
            Live Debug
          </NavLink>

          <NavLink
            to="/debug/branches"
            className={({ isActive }) => linkClasses(isActive)}
          >
            Branches Debug
          </NavLink>
        </div>
      </CardContent>
    </Card>
  );
}
