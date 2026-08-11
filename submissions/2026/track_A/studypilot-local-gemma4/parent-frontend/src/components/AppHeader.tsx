import { ClipboardCheck, ClipboardList, SlidersHorizontal } from "lucide-react";
import { NavLink } from "react-router-dom";

export const PARENT_TABS = [
  { to: "/brief", label: "今日作业单", icon: ClipboardList },
  { to: "/calibration", label: "本周校准", icon: SlidersHorizontal },
  { to: "/result", label: "晚间记录", icon: ClipboardCheck },
] as const;

export function AppHeader() {
  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="brand-row" aria-label="时间规划小助手 家长端">
          <span className="brand-mark">S</span>
          <span className="brand-copy">
            <strong>时间规划小助手</strong>
            <small>家庭工作台</small>
          </span>
        </div>
        <nav className="tab-nav" aria-label="家长工作区">
          {PARENT_TABS.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : undefined)}>
              <Icon size={17} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
