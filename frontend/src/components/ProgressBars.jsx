import { colorForCategory } from "../categoryColors";

export default function ProgressBars({ stats }) {
  if (!stats) return null;
  const entries = Object.entries(stats.by_category);
  if (entries.length === 0) return null;

  return (
    <div className="log-card">
      <div className="log-card-header">
        <span className="log-card-title">Mastery by subject</span>
        <span className="log-card-meta">
          {stats.completed}/{stats.total} total
        </span>
      </div>
      {entries.map(([category, counts]) => {
        const pct = counts.total ? Math.round((counts.completed / counts.total) * 100) : 0;
        const color = colorForCategory(category);
        return (
          <div className="meter-row" key={category}>
            <span className="meter-label">{category}</span>
            <div className="meter-track">
              <div
                className="meter-fill"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
            <span className="meter-count">
              {counts.completed}/{counts.total}
            </span>
          </div>
        );
      })}
    </div>
  );
}
