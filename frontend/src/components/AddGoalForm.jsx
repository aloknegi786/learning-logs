import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../api";

export default function AddGoalForm({ categories, onCreated, showToast }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim()) {
      showToast?.("Please enter a title.", "error");
      return;
    }
    if (!categoryId) {
      showToast?.("Please select a category.", "error");
      return;
    }
    setSubmitting(true);
    try {
      const goal = await api.createGoal({
        title: title.trim(),
        description: description.trim() || null,
        category_id: categoryId,
      });
      onCreated(goal);
      setTitle("");
      setDescription("");
      showToast?.("Added to your log.");
    } catch (err) {
      showToast?.(`Couldn't add goal: ${err.message}`, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="e.g. Implement an LRU cache from scratch"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
      />
      <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
        <option value="">Select a category</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <textarea
        placeholder="Notes / resources (optional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <button className="btn-primary" type="submit" disabled={submitting}>
        <Plus size={15} strokeWidth={2.5} />
        {submitting ? "Adding…" : "Add to log"}
      </button>
    </form>
  );
}