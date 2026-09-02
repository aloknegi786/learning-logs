import { useCallback, useEffect, useState } from "react";
import { Settings, LogOut } from "lucide-react";
import { api } from "./api";
import TodayView from "./components/TodayView";
import AllGoalsView from "./components/AllGoalsView";
import ActivityView from "./components/ActivityView";
import ToastStack, { useToasts } from "./components/Toast";
import ScrollToTopButton from "./components/ScrollToTopButton";
import Footer from "./components/Footer";
import SettingsModal from "./components/SettingsModal";
import Login from "./components/Login";

export default function App() {
  // "loading" | "authenticated" | "unauthenticated"
  const [authState, setAuthState] = useState("loading");
  const [user, setUser] = useState(null);
  const [tab, setTab] = useState("today");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { toasts, showToast, dismiss } = useToasts();

  const checkAuth = useCallback(() => {
    api
      .getMe()
      .then((me) => {
        setUser(me);
        setAuthState("authenticated");
      })
      .catch(() => {
        setUser(null);
        setAuthState("unauthenticated");
      });
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // api.js dispatches this on any 401 — drops back to the login screen from
  // wherever the request happened to fail, not just on initial page load.
  useEffect(() => {
    function handleUnauthorized() {
      setUser(null);
      setAuthState("unauthenticated");
    }
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, []);

  function handleLoggedIn(result) {
    setUser(result.user);
    setAuthState("authenticated");
    if (result.hydrated) {
      showToast("Welcome back — we've loaded your existing progress.");
    } else if (result.is_new_user) {
      showToast("Welcome! We've set you up with a starter curriculum across 7 categories.");
    }
  }

  async function handleLogout() {
    try {
      await api.logout();
    } catch (e) {
      // even if the request itself fails, still drop the local session
    }
    setUser(null);
    setAuthState("unauthenticated");
  }

  if (authState === "loading") {
    return (
      <div className="app-shell">
        <div className="empty-state">Loading…</div>
      </div>
    );
  }

  if (authState === "unauthenticated") {
    return (
      <>
        <Login onLoggedIn={handleLoggedIn} />
        <ToastStack toasts={toasts} dismiss={dismiss} />
      </>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <p className="app-eyebrow">interview prep</p>
        <h1 className="app-title">learning log</h1>
        <p className="app-subtitle">
          One day's worth of CS fundamentals, system design &amp; DSA at a time.
        </p>
        <div className="header-actions">
          <button
            className="settings-btn"
            onClick={() => setSettingsOpen(true)}
            aria-label="Open settings"
          >
            <Settings size={17} />
          </button>
          <button
            className="logout-btn"
            onClick={handleLogout}
            aria-label="Log out"
            title={user?.email}
          >
            <LogOut size={17} />
          </button>
        </div>
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