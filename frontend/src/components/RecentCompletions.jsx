import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { api } from "../api";
import { colorForCategory } from "../categoryColors";

function formatDate(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function RecentCompletions() {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .getRecentCompletions(5)
      .then(setEntries)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="log-card">
        <div className="empty-state">
          Couldn't load recent completions — is the backend running? ({error})
        </div>
      </div>
    );
  }

  if (!entries) {
    return (
      <div className="log-card">
        <div className="empty-state">Loading recent completions…</div>
      </div>
    );
  }

  return (
    <div className="log-card">
      <div className="log-card-header">
        <span className="log-card-title">Recently completed</span>
      </div>

      {entries.length === 0 ? (
        <div className="empty-state">Nothing completed yet — check off your first goal!</div>
      ) : (
        entries.map((e) => {
          const color = colorForCategory(e.category);
          return (
            <div className="goal-row" key={e.goal_id ?? `${e.goal_title}-${e.completed_at}`}>
              <span className="checkbox-btn done" style={{ cursor: "default" }}>
                <CheckCircle2 size={14} strokeWidth={2.5} />
              </span>
              <div className="goal-body">
                <p className="goal-title">{e.goal_title}</p>
                <div className="goal-tags">
                  <span className="category-chip" style={{ color }}>
                    {e.category}
                  </span>
                  <span className="recent-completion-date">{formatDate(e.completed_on)}</span>
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}