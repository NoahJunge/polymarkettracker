import { useState, useEffect, useRef } from "react";
import { getTriggeredAlerts, dismissAlert } from "../api/client";
import { useNavigate } from "react-router-dom";

export default function AlertBell() {
  const [alerts, setAlerts] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  const loadAlerts = async () => {
    try {
      const res = await getTriggeredAlerts();
      setAlerts(res.data);
    } catch {
      // silently fail
    }
  };

  useEffect(() => {
    loadAlerts();
    const interval = setInterval(loadAlerts, 30000);
    return () => clearInterval(interval);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleDismiss = async (alertId, e) => {
    e.stopPropagation();
    await dismissAlert(alertId);
    setAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));
  };

  const formatPrice = (p) => `${(p * 100).toFixed(1)}¢`;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 text-slate-500 hover:text-slate-800"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {alerts.length > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center">
            {alerts.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-80 bg-white border border-slate-200 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
          <div className="p-3 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700">
              Price Alerts
            </h3>
          </div>
          {alerts.length === 0 ? (
            <div className="p-4 text-sm text-slate-400 text-center">
              No triggered alerts
            </div>
          ) : (
            alerts.map((a) => (
              <div
                key={a.alert_id}
                className="p-3 border-b border-slate-50 hover:bg-slate-50 cursor-pointer"
                onClick={() => {
                  navigate(`/markets/${a.market_id}`);
                  setOpen(false);
                }}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-700 truncate">
                      {a.question || a.market_id}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {a.side} {a.condition.toLowerCase()}{" "}
                      {formatPrice(a.threshold)} — hit{" "}
                      {formatPrice(a.triggered_price)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDismiss(a.alert_id, e)}
                    className="ml-2 text-xs text-slate-400 hover:text-slate-600"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
