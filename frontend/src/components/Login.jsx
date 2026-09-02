import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

export default function Login({ onLoggedIn }) {
  const buttonRef = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) {
      setError(
        "VITE_GOOGLE_CLIENT_ID isn't configured — add it to frontend/.env to enable sign-in."
      );
      return;
    }

    async function handleCredential(response) {
      try {
        const result = await api.loginWithGoogle(response.credential);
        onLoggedIn(result);
      } catch (e) {
        setError(`Sign-in failed: ${e.message}`);
      }
    }

    // The GSI script loads async — poll briefly until it's actually ready
    // rather than assuming it's present the instant this component mounts.
    let cancelled = false;
    const interval = setInterval(() => {
      if (cancelled) return;
      if (window.google?.accounts?.id) {
        clearInterval(interval);
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleCredential,
        });
        if (buttonRef.current) {
          window.google.accounts.id.renderButton(buttonRef.current, {
            type: "standard",
            theme: "filled_black",
            size: "large",
            shape: "pill",
            text: "signin_with",
          });
        }
      }
    }, 100);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [onLoggedIn]);

  return (
    <div className="login-screen">
      <div className="login-card">
        <p className="app-eyebrow">interview prep</p>
        <h1 className="app-title">learning log</h1>
        <p className="app-subtitle">
          One day's worth of CS fundamentals, system design &amp; DSA at a time.
        </p>
        <div className="login-button-wrap" ref={buttonRef} />
        {error && <p className="login-error">{error}</p>}
      </div>
    </div>
  );
}