import { useEffect, useState, useCallback } from "react";
import { listApprovals, resolveApproval } from "../api.js";
import RequestCard from "./RequestCard.jsx";
import ChatWidget from "./ChatWidget.jsx";

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
  const [showChat, setShowChat] = useState(false);

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
    setRequests((prev) => prev.filter((r) => (r.issue_key || r.id) !== id));
  }

  return (
    <div className={`dashboard ${showChat ? "with-chat" : ""}`}>
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

      <div className="list">
        {requests.map((r) => (
          <RequestCard key={r.issue_key || r.id} request={r} onResolve={handleResolve} />
        ))}
      </div>

      {showChat && (
        <div className="chat-panel">
          <div className="chat-header">
            <h3>Approvals Assistant</h3>
            <button className="chat-close" onClick={() => setShowChat(false)} aria-label="Close chat">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <ChatWidget />
        </div>
      )}

      {/* Floating chat toggle button */}
      <button
        className="chat-toggle"
        onClick={() => setShowChat(!showChat)}
        aria-label={showChat ? "Close chat" : "Open chat"}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {showChat ? (
            <line x1="18" y1="6" x2="6" y2="18"></line>
          ) : (
            <>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </>
          )}
        </svg>
      </button>
    </div>
  );
}
