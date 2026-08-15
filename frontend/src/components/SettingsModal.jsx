import { useEffect, useState } from "react";
import { api } from "../api";

export default function SettingsModal({ onClose, showToast }) {
  const [count, setCount] = useState(3);
  const [categories, setCategories] = useState([]);
  const [focusCategory, setFocusCategory] = useState(null); // {id, name} | null
  const [focusDaysRemaining, setFocusDaysRemaining] = useState(null);
  const [selectedFocusId, setSelectedFocusId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [focusBusy, setFocusBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.getSettings(), api.getCategories()])
      .then(([s, cats]) => {
        setCount(s.daily_goal_count);
        setFocusCategory(s.focus_category);
        setFocusDaysRemaining(s.focus_days_remaining);
        setCategories(cats);
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

  async function handleSetFocus() {
    if (!selectedFocusId) return;
    setFocusBusy(true);
    try {
      const s = await api.setFocusCategory(selectedFocusId);
      setFocusCategory(s.focus_category);
      setFocusDaysRemaining(s.focus_days_remaining);
      setSelectedFocusId("");
      showToast?.(`Focusing on ${s.focus_category.name} for the next 7 days.`);
    } catch (e) {
      showToast?.(`Couldn't set focus: ${e.message}`, "error");
    } finally {
      setFocusBusy(false);
    }
  }

  async function handleClearFocus() {
    setFocusBusy(true);
    try {
      const s = await api.clearFocusCategory();
      setFocusCategory(s.focus_category);
      setFocusDaysRemaining(s.focus_days_remaining);
      showToast?.("Focus cleared.");
    } catch (e) {
      showToast?.(`Couldn't clear focus: ${e.message}`, "error");
    } finally {
      setFocusBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">Settings</h3>
        <p className="modal-body">
          How many new goals should be surfaced on your home screen each day? The
          first visit of a new day picks that day's set using this count.
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

        <div className="settings-divider" />

        <p className="modal-body">
          Want to lean toward one category for a while? Pick a focus and roughly
          60-70% of each day's picks will come from it, with the rest for variety
          — automatically clears after 7 days, or clear it early any time.
        </p>

        {!loading && focusCategory && (
          <div className="focus-active-banner">
            Focusing on <strong>{focusCategory.name}</strong> —{" "}
            {focusDaysRemaining} day{focusDaysRemaining === 1 ? "" : "s"} left
            <button className="btn-secondary" onClick={handleClearFocus} disabled={focusBusy}>
              Clear focus
            </button>
          </div>
        )}

        {!loading && !focusCategory && (
          <div className="focus-set-row">
            <select
              value={selectedFocusId}
              onChange={(e) => setSelectedFocusId(e.target.value)}
              className="settings-number-input"
              style={{ width: "auto", flex: 1 }}
            >
              <option value="">No focus</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <button
              className="btn-secondary"
              onClick={handleSetFocus}
              disabled={focusBusy || !selectedFocusId}
            >
              Set focus
            </button>
          </div>
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