import { useCallback, useRef, useState } from "react";
import { CheckCircle2, AlertCircle, X } from "lucide-react";

let idCounter = 0;

export function useToasts() {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    clearTimeout(timers.current[id]);
    delete timers.current[id];
  }, []);

  const showToast = useCallback(
    (message, type = "success") => {
      const id = ++idCounter;
      setToasts((prev) => [...prev, { id, message, type }]);
      timers.current[id] = setTimeout(() => dismiss(id), 4000);
    },
    [dismiss]
  );

  return { toasts, showToast, dismiss };
}

export default function ToastStack({ toasts, dismiss }) {
  if (toasts.length === 0) return null;
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div className={`toast ${t.type}`} key={t.id} role="status">
          <span className="toast-icon">
            {t.type === "error" ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
          </span>
          <span>{t.message}</span>
          <button className="toast-dismiss" onClick={() => dismiss(t.id)} aria-label="Dismiss">
            <X size={15} />
          </button>
        </div>
      ))}
    </div>
  );
}
