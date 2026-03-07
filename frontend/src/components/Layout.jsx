import { NavLink } from "react-router-dom";
import AlertBell from "./AlertBell";

const DashboardIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </svg>
);

const DiscoveryIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.35-4.35" />
  </svg>
);

const PaperTradingIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
    <polyline points="16 7 22 7 22 13" />
  </svg>
);

const DatabaseIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const navItems = [
  { to: "/", label: "Dashboard", Icon: DashboardIcon },
  { to: "/discovery", label: "Discovery", Icon: DiscoveryIcon },
  { to: "/paper-trading", label: "Paper Trading", Icon: PaperTradingIcon },
  { to: "/database", label: "Database", Icon: DatabaseIcon },
  { to: "/settings", label: "Settings", Icon: SettingsIcon },
];

export default function Layout({ children }) {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar — light theme */}
      <nav className="w-60 flex-shrink-0 flex flex-col bg-white border-r border-slate-200">
        {/* Brand */}
        <div className="px-4 py-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 shadow-sm"
              style={{ background: "linear-gradient(135deg, #7c3aed, #6d28d9)" }}
            >
              <span className="text-white text-xs font-bold tracking-tight">PM</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-900 leading-tight">Polymarket</h1>
              <p className="text-xs text-slate-400 leading-tight">Trump Tracker</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <ul className="mt-2 px-2 flex-1 space-y-0.5">
          {navItems.map(({ to, label, Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                    isActive
                      ? "bg-violet-600 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`
                }
              >
                <Icon />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>

        {/* Footer */}
        <div className="px-4 py-4 border-t border-slate-100">
          <p className="text-xs text-slate-400">Data: Polymarket Gamma API</p>
        </div>
      </nav>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 border-b border-slate-200 flex items-center justify-between px-6 bg-white/80 backdrop-blur-sm flex-shrink-0">
          <div />
          <AlertBell />
        </header>
        <main
          className="flex-1 p-6 overflow-auto"
          style={{
            backgroundColor: "#f1f5f9",
            backgroundImage: [
              "radial-gradient(ellipse at 18% 12%, rgba(124, 58, 237, 0.1) 0%, transparent 48%)",
              "radial-gradient(ellipse at 82% 88%, rgba(79, 70, 229, 0.07) 0%, transparent 48%)",
              "radial-gradient(circle, #c4cdd9 1.5px, transparent 1.5px)",
            ].join(", "),
            backgroundSize: "100% 100%, 100% 100%, 26px 26px",
            backgroundAttachment: "fixed, fixed, local",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
