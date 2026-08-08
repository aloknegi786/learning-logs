import { useEffect, useState } from "react";
import { X, Link2, Trash2, Pencil, Plus } from "lucide-react";
import { api } from "../api";
import { colorForCategory } from "../categoryColors";
import ConfirmModal from "./ConfirmModal";

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function JournalModal({ goal, onClose, onEntryCountChange, showToast }) {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);

  const [content, setContent] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [editingId, setEditingId] = useState(null);
  const [editContent, setEditContent] = useState("");
  const [editLinkUrl, setEditLinkUrl] = useState("");
  const [editLinkLabel, setEditLinkLabel] = useState("");

  const [pendingDelete, setPendingDelete] = useState(null);

  useEffect(() => {
    api
      .listEntries(goal.id)
      .then(setEntries)
      .catch((e) => setError(e.message));
  }, [goal.id]);

  async function handleAdd(e) {
    e.preventDefault();
    if (!content.trim() && !linkUrl.trim()) {
      showToast?.("Add a note or a link first.", "error");
      return;
    }
    setSubmitting(true);
    try {
      const entry = await api.createEntry(goal.id, {
        content: content.trim() || null,
        link_url: linkUrl.trim() || null,
        link_label: linkLabel.trim() || null,
      });
      setEntries((prev) => {
        const next = [entry, ...(prev || [])];
        onEntryCountChange?.(goal.id, next.length);
        return next;
      });
      setContent("");
      setLinkUrl("");
      setLinkLabel("");
      showToast?.("Added to your journal.");
    } catch (err) {
      showToast?.(`Couldn't add entry: ${err.message}`, "error");
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(entry) {
    setEditingId(entry.id);
    setEditContent(entry.content || "");
    setEditLinkUrl(entry.link_url || "");
    setEditLinkLabel(entry.link_label || "");
  }

  async function saveEdit(entryId) {
    if (!editContent.trim() && !editLinkUrl.trim()) {
      showToast?.("An entry needs a note or a link.", "error");
      return;
    }
    try {
      const updated = await api.updateEntry(entryId, {
        content: editContent.trim() || null,
        link_url: editLinkUrl.trim() || null,
        link_label: editLinkLabel.trim() || null,
      });
      setEntries((prev) => prev.map((e) => (e.id === entryId ? updated : e)));
      setEditingId(null);
      showToast?.("Entry updated.");
    } catch (err) {
      showToast?.(`Couldn't update entry: ${err.message}`, "error");
    }
  }

  async function confirmDeleteEntry() {
    const entry = pendingDelete;
    setPendingDelete(null);
    setEntries((prev) => {
      const next = prev.filter((e) => e.id !== entry.id);
      onEntryCountChange?.(goal.id, next.length);
      return next;
    });
    try {
      await api.deleteEntry(entry.id);
      showToast?.("Entry removed.");
    } catch (err) {
      showToast?.(`Couldn't delete entry: ${err.message}`, "error");
    }
  }

  const color = colorForCategory(goal.category);

  return (
    <>
      <div className="modal-backdrop" onClick={onClose}>
        <div className="modal-card journal-modal" onClick={(e) => e.stopPropagation()}>
          <div className="journal-header">
            <div>
              <h3 className="modal-title">{goal.title}</h3>
              <span className="category-chip" style={{ color }}>
                {goal.category}
              </span>
            </div>
            <button className="journal-close" onClick={onClose} aria-label="Close journal">
              <X size={18} />
            </button>
          </div>

          {goal.description && (
            <p className="journal-original-note">{goal.description}</p>
          )}

          <form className="journal-add-form" onSubmit={handleAdd}>
            <textarea
              placeholder="Notes / reflection…"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <input
              type="text"
              placeholder="Link label (optional) — e.g. Lecture: MIT 6.006"
              value={linkLabel}
              onChange={(e) => setLinkLabel(e.target.value)}
            />
            <input
              type="url"
              placeholder="https://... (blog post, video, docs)"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
            />
            <button className="btn-primary" type="submit" disabled={submitting}>
              <Plus size={15} strokeWidth={2.5} />
              {submitting ? "Adding…" : "Add to journal"}
            </button>
          </form>

          <div className="journal-entries">
            {error && (
              <div className="empty-state">
                Couldn't load journal — is the backend running? ({error})
              </div>
            )}
            {!error && !entries && <div className="empty-state">Loading journal…</div>}
            {entries && entries.length === 0 && (
              <div className="empty-state">No entries yet — add your first note or link above.</div>
            )}
            {entries &&
              entries.map((entry) => (
                <div className="journal-entry" key={entry.id}>
                  {editingId === entry.id ? (
                    <div className="journal-edit-form">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        placeholder="Notes / reflection…"
                      />
                      <input
                        type="text"
                        placeholder="Link label"
                        value={editLinkLabel}
                        onChange={(e) => setEditLinkLabel(e.target.value)}
                      />
                      <input
                        type="url"
                        placeholder="Link URL"
                        value={editLinkUrl}
                        onChange={(e) => setEditLinkUrl(e.target.value)}
                      />
                      <div className="journal-edit-actions">
                        <button className="btn-secondary" onClick={() => setEditingId(null)}>
                          Cancel
                        </button>
                        <button className="btn-primary" onClick={() => saveEdit(entry.id)}>
                          Save
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="journal-entry-meta">
                        <span>{formatDate(entry.created_at)}</span>
                        <div className="journal-entry-actions">
                          <button onClick={() => startEdit(entry)} aria-label="Edit entry">
                            <Pencil size={14} />
                          </button>
                          <button onClick={() => setPendingDelete(entry)} aria-label="Delete entry">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                      {entry.content && <p className="journal-entry-content">{entry.content}</p>}
                      {entry.link_url && (
                        <a
                          className="journal-entry-link"
                          href={entry.link_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <Link2 size={13} />
                          {entry.link_label || entry.link_url}
                        </a>
                      )}
                    </>
                  )}
                </div>
              ))}
          </div>
        </div>
      </div>

      {pendingDelete && (
        <ConfirmModal
          title="Remove this entry?"
          body="This journal entry will be permanently removed."
          confirmLabel="Remove"
          onConfirm={confirmDeleteEntry}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </>
  );
}
