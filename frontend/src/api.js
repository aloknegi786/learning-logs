const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include", // sends the httpOnly session cookie cross-origin
    ...options,
  });
  if (res.status === 401) {
    // session missing/expired — let App.jsx drop back to the login screen
    // from wherever the request happened to fail, instead of every caller
    // needing its own 401-handling logic.
    window.dispatchEvent(new CustomEvent("auth:unauthorized"));
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // auth
  loginWithGoogle: (idToken) =>
    request("/auth/google", { method: "POST", body: JSON.stringify({ id_token: idToken }) }),
  logout: () => request("/auth/logout", { method: "POST" }),
  getMe: () => request("/auth/me"),

  getToday: () => request("/today"),
  getGoals: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/goals${qs ? `?${qs}` : ""}`);
  },
  getGoalDetail: (id) => request(`/goals/${id}`),
  createGoal: (goal) =>
    request("/goals", { method: "POST", body: JSON.stringify(goal) }),
  updateGoal: (id, updates) =>
    request(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(updates) }),
  deleteGoal: (id) => request(`/goals/${id}`, { method: "DELETE" }),
  getCategories: () => request("/categories"),
  getStats: () => request("/stats"),

  // journal entries (per-goal learning journey: notes + resource links)
  listEntries: (goalId) => request(`/goals/${goalId}/entries`),
  createEntry: (goalId, entry) =>
    request(`/goals/${goalId}/entries`, { method: "POST", body: JSON.stringify(entry) }),
  updateEntry: (entryId, updates) =>
    request(`/entries/${entryId}`, { method: "PATCH", body: JSON.stringify(updates) }),
  deleteEntry: (entryId) => request(`/entries/${entryId}`, { method: "DELETE" }),

  // settings
  getSettings: () => request("/settings"),
  updateSettings: (updates) =>
    request("/settings", { method: "PUT", body: JSON.stringify(updates) }),
  setFocusCategory: (categoryId) =>
    request("/settings/focus", { method: "POST", body: JSON.stringify({ category_id: categoryId }) }),
  clearFocusCategory: () => request("/settings/focus", { method: "DELETE" }),

  // activity heatmap
  getHeatmap: (days = 182) => request(`/activity/heatmap?days=${days}`),
  getRecentCompletions: (limit = 5) => request(`/activity/recent?limit=${limit}`),
  regenerateToday: () => request("/today/regenerate", { method: "POST" }),
};