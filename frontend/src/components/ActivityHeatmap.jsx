import { Fragment, useEffect, useState } from "react";
import { api } from "../api";

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function getLevel(count) {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  if (count <= 4) return 3;
  return 4;
}

// Splits the flat, chronological day list into one group per calendar
// month (days are already sorted, so same year+month days are always
// contiguous — no need to re-sort).
function groupDaysByMonth(days) {
  const groups = [];
  days.forEach((day) => {
    const d = new Date(`${day.date}T00:00:00`);
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    const last = groups[groups.length - 1];
    if (!last || last.key !== key) {
      groups.push({ key, label: MONTH_LABELS[d.getMonth()], days: [day] });
    } else {
      last.days.push(day);
    }
  });
  return groups;
}

// Builds this month's OWN independent set of columns: leading blanks so the
// first real day lands on its true weekday row, and trailing blanks so the
// last column is padded out to a full 7 rows — never borrowing or lending
// days to/from a neighboring month's columns.
function buildMonthColumns(monthDays) {
  const first = new Date(`${monthDays[0].date}T00:00:00`);
  const leadingBlanks = first.getDay(); // 0 = Sunday
  const padded = [...Array(leadingBlanks).fill(null), ...monthDays];
  const remainder = padded.length % 7;
  if (remainder !== 0) {
    padded.push(...Array(7 - remainder).fill(null));
  }
  const columns = [];
  for (let i = 0; i < padded.length; i += 7) {
    columns.push(padded.slice(i, i + 7));
  }
  return columns;
}

function formatTooltipDate(day) {
  return new Date(`${day.date}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function ActivityHeatmap() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [hovered, setHovered] = useState(null); // { day, x, y }

  useEffect(() => {
    api
      .getHeatmap(365)
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="log-card">
        <div className="empty-state">
          Couldn't load activity — is the backend running? ({error})
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="log-card">
        <div className="empty-state">Loading activity…</div>
      </div>
    );
  }

  const monthGroups = groupDaysByMonth(data.days).map((g) => ({
    label: g.label,
    columns: buildMonthColumns(g.days),
  }));
  const activeDays = data.days.filter((d) => d.count > 0).length;

  function handleEnter(e, day) {
    if (!day) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setHovered({ day, x: rect.left + rect.width / 2, y: rect.top });
  }

  return (
    <div className="log-card">
      <div className="heatmap-summary">
        <div className="heatmap-summary-count">
          <span className="heatmap-count">{data.total_completions}</span>
          <span className="heatmap-count-label">
            goal{data.total_completions === 1 ? "" : "s"} completed in the past year
          </span>
        </div>
        <div className="heatmap-stats">
          <span>
            Total active days: <strong>{activeDays}</strong>
          </span>
          <span>
            Current streak: <strong>{data.current_streak}</strong>
          </span>
          <span>
            Longest streak: <strong>{data.longest_streak}</strong>
          </span>
        </div>
      </div>

      <div className="heatmap-scroll">
        <div className="heatmap-inner">
          <div className="heatmap-months">
            {monthGroups.map((g, gi) => (
              <Fragment key={gi}>
                <span className="heatmap-month-label" style={{ flexGrow: g.columns.length }}>
                  {g.label}
                </span>
                {gi < monthGroups.length - 1 && <span className="heatmap-month-gap" />}
              </Fragment>
            ))}
          </div>
          <div className="heatmap-grid">
            {monthGroups.map((g, gi) => (
              <Fragment key={gi}>
                {g.columns.map((column, ci) => (
                  <div className="heatmap-col" key={ci}>
                    {column.map((day, di) => (
                      <div
                        key={di}
                        className={`heatmap-cell level-${day ? getLevel(day.count) : "empty"} ${
                          day?.perfect_day ? "perfect" : ""
                        }`}
                        onMouseEnter={(e) => handleEnter(e, day)}
                        onMouseLeave={() => setHovered(null)}
                      />
                    ))}
                  </div>
                ))}
                {gi < monthGroups.length - 1 && <div className="heatmap-month-gap" />}
              </Fragment>
            ))}
          </div>
        </div>
      </div>

      <div className="heatmap-legend">
        <span>Less</span>
        {[0, 1, 2, 3, 4].map((l) => (
          <div key={l} className={`heatmap-cell legend-swatch level-${l}`} />
        ))}
        <span>More</span>
      </div>

      {hovered && (
        <div className="heatmap-tooltip" style={{ left: hovered.x, top: hovered.y }}>
          <strong>{hovered.day.count}</strong> goal{hovered.day.count === 1 ? "" : "s"} completed
          <br />
          {formatTooltipDate(hovered.day)}
          {hovered.day.perfect_day && (
            <>
              <br />
              <span className="tooltip-perfect">Full daily plan cleared</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}