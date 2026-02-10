import { NavLink } from "react-router-dom";
import AlertBell from "./AlertBell";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/discovery", label: "Discovery" },
  { to: "/paper-trading", label: "Paper Trading" },
  { to: "/database", label: "Database" },
  { to: "/settings", label: "Settings" },
];

export default function Layout({ children }) {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <nav className="w-56 bg-slate-900 text-white flex-shrink-0">
        <div className="p-4 border-b border-slate-700">
          <h1 className="text-lg font-bold">Polymarket Tracker</h1>
          <p className="text-xs text-slate-400 mt-1">Trump Markets</p>
        </div>
        <ul className="mt-2">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `block px-4 py-2.5 text-sm transition-colors ${
                    isActive
                      ? "bg-slate-700 text-white font-medium"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Top bar */}
        <header className="h-12 border-b border-slate-200 flex items-center justify-end px-4 bg-white">
          <AlertBell />
        </header>
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
