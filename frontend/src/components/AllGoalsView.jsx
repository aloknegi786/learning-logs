import { useEffect, useRef, useState } from "react";
import { Check, Trash2, NotebookPen } from "lucide-react";
import { api } from "../api";
import { colorForCategory } from "../categoryColors";
import AddGoalForm from "./AddGoalForm";
import ProgressBars from "./ProgressBars";
import ConfirmModal from "./ConfirmModal";
import ScrollToTopButton from "./ScrollToTopButton";
import JournalModal from "./JournalModal";

export default function AllGoalsView({ showToast }) {
  const [goals, setGoals] = useState(null);
  const [categories, setCategories] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [journalGoal, setJournalGoal] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    Promise.all([api.getGoals(), api.getCategories(), api.getStats()])
      .then(([g, c, s]) => {
        setGoals(g);
        setCategories(c);
        setStats(s);
      })
      .catch((e) => setError(e.message));
  }, []);

  function refreshStats() {
    api.getStats().then(setStats).catch(() => {});
  }

  async function toggle(goal) {
    const nextStatus = goal.status === "completed" ? "pending" : "completed";
    setGoals((prev) =>
      prev.map((g) => (g.id === goal.id ? { ...g, status: nextStatus } : g))
    );
    try {
      await api.updateGoal(goal.id, { status: nextStatus });
      refreshStats();
    } catch (e) {
      setGoals((prev) =>
        prev.map((g) => (g.id === goal.id ? { ...g, status: goal.status } : g))
      );
      showToast?.("Couldn't save that change — reverted.", "error");
    }
  }

  async function confirmDelete() {
    const goal = pendingDelete;
    setPendingDelete(null);
    setGoals((prev) => prev.filter((g) => g.id !== goal.id));
    try {
      await api.deleteGoal(goal.id);
      refreshStats();
      showToast?.("Goal removed.");
    } catch (e) {
      showToast?.(`Couldn't delete: ${e.message}`, "error");
    }
  }

  function handleCreated(goal) {
    setGoals((prev) => (prev ? [...prev, goal] : [goal]));
    refreshStats();
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
        <div className="empty-state">Loading your log…</div>
      </div>
    );
  }

  const visible =
    filter === "all" ? goals : goals.filter((g) => g.category === filter);

  return (
    <>
      <div className="two-col-layout">
        <div className="col-left">
          <div className="log-card">
            <div className="log-card-header">
              <span className="log-card-title">Append a new goal</span>
            </div>
            <AddGoalForm categories={categories} onCreated={handleCreated} showToast={showToast} />
          </div>

          <ProgressBars stats={stats} />
        </div>

        <div className="col-right">
          <div className="scroll-pane-wrap">
            <div className="scroll-pane" ref={scrollRef}>
              <div className="section-label">All goals</div>

              <div className="filter-pills">
                <button
                  className={`filter-pill ${filter === "all" ? "active" : ""}`}
                  onClick={() => setFilter("all")}
                >
                  All ({goals.length})
                </button>
                {categories.map((c) => (
                  <button
                    key={c}
                    className={`filter-pill ${filter === c ? "active" : ""}`}
                    onClick={() => setFilter(c)}
                  >
                    {c}
                  </button>
                ))}
              </div>

              <div className="log-card">
                {visible.length === 0 ? (
                  <div className="empty-state">Nothing here yet.</div>
                ) : (
                  visible.map((g) => {
                    const isDone = g.status === "completed";
                    const color = colorForCategory(g.category);
                    return (
                      <div className="goal-row" key={g.id}>
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
                        <button
                          className="delete-btn"
                          onClick={() => setPendingDelete(g)}
                          aria-label="Delete goal"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
            <ScrollToTopButton containerRef={scrollRef} />
          </div>
        </div>
      </div>

      {pendingDelete && (
        <ConfirmModal
          title="Remove this goal?"
          body={`"${pendingDelete.title}" will be permanently removed from your log.`}
          confirmLabel="Remove"
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      )}

      {journalGoal && (
        <JournalModal
          goal={journalGoal}
          onClose={() => setJournalGoal(null)}
          onEntryCountChange={handleEntryCountChange}
          showToast={showToast}
        />
      )}
    </>
  );
}
