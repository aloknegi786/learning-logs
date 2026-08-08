import { useEffect, useState } from "react";
import { api } from "../api";

export default function SettingsModal({ onClose, showToast }) {
  const [count, setCount] = useState(3);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setCount(s.daily_goal_count);
        setLoading(false);
      })
      .catch((e) => {
        showToast?.(`Couldn't load settings: ${e.message}`, "error");
        setLoading(false);
      });
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      await api.updateSettings({ daily_goal_count: count });
      showToast?.("Settings saved — takes effect from tomorrow's picks.");
      onClose();
    } catch (e) {
      showToast?.(`Couldn't save settings: ${e.message}`, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">Settings</h3>
        <p className="modal-body">
          How many new goals should be surfaced on your home screen each day? The
          3 AM job (or, if that hasn't run yet, opening the app) uses this count.
        </p>
        {!loading && (
          <input
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="settings-number-input"
          />
        )}
        <div className="modal-actions" style={{ marginTop: 20 }}>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleSave} disabled={saving || loading}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
