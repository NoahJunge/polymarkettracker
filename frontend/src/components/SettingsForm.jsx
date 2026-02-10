import { useState, useEffect } from "react";
import { getSettings, updateSettings, runCollector, getJobStatus, getExports } from "../api/client";

export default function SettingsForm() {
  const [settings, setSettings] = useState(null);
  const [status, setStatus] = useState(null);
  const [exports, setExports] = useState([]);
  const [saving, setSaving] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [message, setMessage] = useState(null);

  const load = async () => {
    try {
      const [sRes, jRes, eRes] = await Promise.all([
        getSettings(),
        getJobStatus(),
        getExports(),
      ]);
      setSettings(sRes.data);
      setStatus(jRes.data);
      setExports(eRes.data);
    } catch (err) {
      console.error("Failed to load settings", err);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await updateSettings(settings);
      setMessage("Settings saved");
    } catch (err) {
      setMessage("Failed to save: " + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async () => {
    setCollecting(true);
    setMessage(null);
    try {
      const res = await runCollector();
      setMessage(
        `Collection complete: ${res.data.discovered} discovered, ${res.data.snapshots} snapshots`,
      );
      await load();
    } catch (err) {
      setMessage("Collection failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setCollecting(false);
    }
  };

  if (!settings) return <p className="text-slate-500">Loading settings...</p>;

  return (
    <div className="space-y-6">
      {/* Collector Settings */}
      <section className="bg-white rounded-lg border border-slate-200 p-5">
        <h3 className="text-base font-semibold mb-4">Collector Settings</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.collector_enabled}
              onChange={(e) =>
                setSettings({ ...settings, collector_enabled: e.target.checked })
              }
              className="rounded"
            />
            <span className="text-sm">Collector Enabled</span>
          </label>

          <div>
            <label className="text-sm font-medium">Interval (minutes)</label>
            <input
              type="number"
              min="1"
              value={settings.collector_interval_minutes}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  collector_interval_minutes: Number(e.target.value),
                })
              }
              className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Cron Expression (optional)</label>
            <input
              type="text"
              value={settings.cron_expression || ""}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  cron_expression: e.target.value || null,
                })
              }
              placeholder="e.g. */30 * * * *"
              className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Max Events Per Tag</label>
            <input
              type="number"
              min="1"
              value={settings.max_events_per_tag}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  max_events_per_tag: Number(e.target.value),
                })
              }
              className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm mt-1"
            />
          </div>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.require_binary_yes_no}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  require_binary_yes_no: e.target.checked,
                })
              }
              className="rounded"
            />
            <span className="text-sm">Require Binary Yes/No</span>
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.export_enabled}
              onChange={(e) =>
                setSettings({ ...settings, export_enabled: e.target.checked })
              }
              className="rounded"
            />
            <span className="text-sm">Export Enabled</span>
          </label>
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium">Trump Keywords (comma-separated)</label>
          <input
            type="text"
            value={(settings.trump_keywords || []).join(", ")}
            onChange={(e) =>
              setSettings({
                ...settings,
                trump_keywords: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
            className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm mt-1"
          />
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium">Force Tracked IDs (comma-separated)</label>
          <input
            type="text"
            value={(settings.force_tracked_ids || []).join(", ")}
            onChange={(e) =>
              setSettings({
                ...settings,
                force_tracked_ids: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
            className="w-full border border-slate-300 rounded px-3 py-1.5 text-sm mt-1"
          />
        </div>

        <div className="mt-4 flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
          <button
            onClick={handleRunNow}
            disabled={collecting}
            className="px-4 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
          >
            {collecting ? "Running..." : "Run Collector Now"}
          </button>
        </div>

        {message && (
          <p className="mt-3 text-sm text-slate-700 bg-slate-50 rounded p-2">
            {message}
          </p>
        )}
      </section>

      {/* Job Status */}
      {status && (
        <section className="bg-white rounded-lg border border-slate-200 p-5">
          <h3 className="text-base font-semibold mb-3">Scheduler Status</h3>
          <div className="text-sm space-y-1">
            <p>
              <span className="text-slate-500">Running:</span>{" "}
              {status.running ? "Yes" : "No"}
            </p>
            <p>
              <span className="text-slate-500">Last Run:</span>{" "}
              {status.last_run_utc
                ? new Date(status.last_run_utc).toLocaleString()
                : "Never"}
            </p>
            {status.last_run_stats && (
              <>
                <p>
                  <span className="text-slate-500">Discovered:</span>{" "}
                  {status.last_run_stats.discovered}
                </p>
                <p>
                  <span className="text-slate-500">Snapshots:</span>{" "}
                  {status.last_run_stats.snapshots}
                </p>
                <p>
                  <span className="text-slate-500">Duration:</span>{" "}
                  {status.last_run_stats.duration_seconds?.toFixed(1)}s
                </p>
              </>
            )}
            {status.jobs?.map((j) => (
              <p key={j.id}>
                <span className="text-slate-500">{j.name}:</span> next at{" "}
                {j.next_run_time
                  ? new Date(j.next_run_time).toLocaleString()
                  : "—"}
              </p>
            ))}
          </div>
        </section>
      )}

      {/* Export Files */}
      {exports.length > 0 && (
        <section className="bg-white rounded-lg border border-slate-200 p-5">
          <h3 className="text-base font-semibold mb-3">Export Files</h3>
          <div className="text-sm space-y-1">
            {exports.map((f) => (
              <p key={f.filename}>
                {f.filename}{" "}
                <span className="text-slate-400">
                  ({(f.size_bytes / 1024).toFixed(1)} KB)
                </span>
              </p>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
