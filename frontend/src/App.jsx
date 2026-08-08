import { useState } from "react";
import { Settings } from "lucide-react";
import TodayView from "./components/TodayView";
import AllGoalsView from "./components/AllGoalsView";
import ActivityView from "./components/ActivityView";
import ToastStack, { useToasts } from "./components/Toast";
import ScrollToTopButton from "./components/ScrollToTopButton";
import Footer from "./components/Footer";
import SettingsModal from "./components/SettingsModal";

export default function App() {
  const [tab, setTab] = useState("today");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { toasts, showToast, dismiss } = useToasts();

  return (
    <div className="app-shell">
      <header className="app-header">
        <p className="app-eyebrow">interview prep</p>
        <h1 className="app-title">learning log</h1>
        <p className="app-subtitle">
          One day's worth of CS fundamentals, system design &amp; DSA at a time.
        </p>
        <button
          className="settings-btn"
          onClick={() => setSettingsOpen(true)}
          aria-label="Open settings"
        >
          <Settings size={17} />
        </button>
      </header>

      <nav className="tabs">
        <button
          className={`tab ${tab === "today" ? "active" : ""}`}
          onClick={() => setTab("today")}
        >
          Today
        </button>
        <button
          className={`tab ${tab === "all" ? "active" : ""}`}
          onClick={() => setTab("all")}
        >
          All goals
        </button>
        <button
          className={`tab ${tab === "activity" ? "active" : ""}`}
          onClick={() => setTab("activity")}
        >
          Activity
        </button>
      </nav>

      <div className="app-main">
        {/* All three views stay mounted permanently — switching tabs just
            hides/shows them via CSS, so each keeps whatever it already
            fetched instead of refetching (and re-showing a spinner) every
            time you come back to it. `display: contents` on the wrapper
            means it doesn't add an extra box to the layout — the visible
            view's actual root element still sits directly inside
            .app-main, exactly as before. */}
        <div style={{ display: tab === "today" ? "contents" : "none" }}>
          <TodayView showToast={showToast} />
        </div>
        <div style={{ display: tab === "all" ? "contents" : "none" }}>
          <AllGoalsView showToast={showToast} />
        </div>
        <div style={{ display: tab === "activity" ? "contents" : "none" }}>
          <ActivityView />
        </div>
      </div>

      <Footer />

      <ToastStack toasts={toasts} dismiss={dismiss} />
      <ScrollToTopButton />

      {settingsOpen && (
        <SettingsModal onClose={() => setSettingsOpen(false)} showToast={showToast} />
      )}
    </div>
  );
}