import { useEffect, useRef, useState } from "react";
import { Check, NotebookPen } from "lucide-react";
import { api } from "../api";
import { colorForCategory } from "../categoryColors";
import ScrollToTopButton from "./ScrollToTopButton";
import JournalModal from "./JournalModal";

function todayLabel() {
  return new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

function ProgressRing({ done, total, size = 34 }) {
  const stroke = 4;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = total ? done / total : 0;
  const offset = circumference * (1 - pct);

  return (
    <svg width={size} height={size} className="progress-ring">
      <circle
        className="progress-ring-track"
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeWidth={stroke}
      />
      <circle
        className="progress-ring-fill"
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeWidth={stroke}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
      />
    </svg>
  );
}

const SOURCE_LABELS = {
  llm: "AI-picked",
  fallback_history: "Based on recent activity",
  fallback_round_robin: "Round robin",
};

function GoalRow({ g, toggle, setJournalGoal }) {
  const isDone = g.status === "completed";
  const color = colorForCategory(g.category);
  return (
    <div className="goal-row">
      <button
        className={`checkbox-btn ${isDone ? "done" : ""}`}
        onClick={() => toggle(g)}
        aria-label={isDone ? "Mark as not done" : "Mark as done"}
      >
        {isDone && <Check size={14} strokeWidth={3} />}
      </button>
      <div className="goal-body">
        <p className={`goal-title ${isDone ? "done" : ""}`}>{g.title}</p>
        <div className="goal-tags">
          <span className="category-chip" style={{ color }}>
            {g.category}
          </span>
        </div>
      </div>
      <button
        className={`journal-btn ${g.entry_count > 0 ? "has-entries" : ""}`}
        onClick={() => setJournalGoal(g)}
        aria-label="Open learning journal"
      >
        <NotebookPen size={13} />
        {g.entry_count > 0 && g.entry_count}
      </button>
    </div>
  );
}

export default function TodayView({ showToast }) {
  const [goals, setGoals] = useState(null);
  const [source, setSource] = useState(null);
  const [focusCategory, setFocusCategory] = useState(null);
  const [error, setError] = useState(null);
  const [journalGoal, setJournalGoal] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    load();
  }, []);

  function load() {
    api
      .getToday()
      .then((res) => {
        setGoals(res.goals);
        setSource(res.source);
        setFocusCategory(res.focus_category);
        if (res.note) showToast?.(res.note, "info");
      })
      .catch((e) => setError(e.message));
  }

  async function toggle(goal) {
    const nextStatus = goal.status === "completed" ? "pending" : "completed";
    setGoals((prev) =>
      prev.map((g) => (g.id === goal.id ? { ...g, status: nextStatus } : g))
    );
    try {
      await api.updateGoal(goal.id, { status: nextStatus });
    } catch (e) {
      load();
      showToast?.("Couldn't save that change — reverted.", "error");
    }
  }

  function handleEntryCountChange(goalId, count) {
    setGoals((prev) =>
      prev ? prev.map((g) => (g.id === goalId ? { ...g, entry_count: count } : g)) : prev
    );
  }

  if (error) {
    return (
      <div className="log-card">
        <div className="empty-state">
          Couldn't reach the API — is the backend running? ({error})
        </div>
      </div>
    );
  }

  if (!goals) {
    return (
      <div className="log-card">
        <div className="empty-state">Loading today's session…</div>
      </div>
    );
  }

  const done = goals.filter((g) => g.status === "completed").length;
  const focusGoals = focusCategory ? goals.filter((g) => g.category === focusCategory) : [];
  const nudgeGoals = focusCategory ? goals.filter((g) => g.category !== focusCategory) : [];

  return (
    <div className="scroll-pane-wrap">
      <div className="scroll-pane" ref={scrollRef}>
        <div className="log-card">
          <div className="log-card-header">
            <span className="log-card-title">Today's session — {todayLabel()}</span>
            <div className="ring-wrap">
              {source && (
                <span className={`source-badge ${source === "llm" ? "llm" : ""}`}>
                  {SOURCE_LABELS[source] || source}
                </span>
              )}
              <span className="log-card-meta">
                {done}/{goals.length} done
              </span>
              <ProgressRing done={done} total={goals.length} />
            </div>
          </div>

          {goals.length === 0 ? (
            <div className="empty-state">
              No pending goals left — add more under "All goals" 🎉
            </div>
          ) : focusCategory ? (
            <>
              {focusGoals.length > 0 && (
                <>
                  <div className="today-section-label">This week's focus</div>
                  {focusGoals.map((g) => (
                    <GoalRow key={g.id} g={g} toggle={toggle} setJournalGoal={setJournalGoal} />
                  ))}
                </>
              )}
              {nudgeGoals.length > 0 && (
                <>
                  <div className="today-section-label">For variety</div>
                  {nudgeGoals.map((g) => (
                    <GoalRow key={g.id} g={g} toggle={toggle} setJournalGoal={setJournalGoal} />
                  ))}
                </>
              )}
            </>
          ) : (
            goals.map((g) => (
              <GoalRow key={g.id} g={g} toggle={toggle} setJournalGoal={setJournalGoal} />
            ))
          )}
        </div>
      </div>
      <ScrollToTopButton containerRef={scrollRef} />

      {journalGoal && (
        <JournalModal
          goal={journalGoal}
          onClose={() => setJournalGoal(null)}
          onEntryCountChange={handleEntryCountChange}
          showToast={showToast}
        />
      )}
    </div>
  );
}