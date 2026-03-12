import { useEffect } from "react";
import "@/App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function App() {
  useEffect(() => {
    const target = `${BACKEND_URL}/api/`;
    window.location.replace(target);
  }, []);

  return (
    <main className="redirect-shell" data-testid="frontend-redirect-shell">
      <h1 data-testid="frontend-redirect-title">Launching Park Vision…</h1>
      <p data-testid="frontend-redirect-message">
        If you are not redirected automatically, continue below.
      </p>
      <a
        href={`${BACKEND_URL}/api/`}
        className="redirect-link"
        data-testid="frontend-redirect-link"
      >
        Open Park Vision
      </a>
    </main>
  );
}
