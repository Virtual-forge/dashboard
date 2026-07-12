import { useEffect, useState, useCallback } from "react";
import { listApprovals, resolveApproval } from "../api.js";
import RequestCard from "./RequestCard.jsx";

const TABS = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Blocked" },
  { key: "all", label: "All" },
];

export default function Dashboard({ email, onLogout }) {
  const [tab, setTab] = useState("pending");
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listApprovals(tab);
      setRequests(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000); // poll every 15s for new requests
    return () => clearInterval(interval);
  }, [load]);

  async function handleResolve(id, decision) {
    await resolveApproval(id, decision);
    // Remove it from the current pending list immediately, or refresh otherwise
    setRequests((prev) => prev.filter((r) => r.id !== id));
  }

  return (
    <div className="dashboard">
      <header>
        <h1>Approval Dashboard</h1>
        <div className="header-right">
          <span className="me">{email}</span>
          <button className="logout" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={tab === t.key ? "active" : ""}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
        <button className="refresh" onClick={load} title="Refresh">
          ⟳
        </button>
      </nav>

      {error && <div className="error">{error}</div>}
      {loading && requests.length === 0 && <p className="empty">Loading…</p>}
      {!loading && requests.length === 0 && !error && (
        <p className="empty">No {tab === "all" ? "" : tab} requests.</p>
      )}

      <div className="grid">
        {requests.map((r) => (
          <RequestCard key={r.id} request={r} onResolve={handleResolve} />
        ))}
      </div>
    </div>
  );
}
