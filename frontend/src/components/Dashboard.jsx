import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { listApprovals, resolveApproval } from "../api.js";
import RequestCard from "./RequestCard.jsx";
import ChatWidget from "./ChatWidget.jsx";
import AgentRequestChart from "./AgentRequestChart.jsx";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard" },
  { id: "approvals", label: "Approvals", icon: "approvals" },
  { id: "settings", label: "Settings", icon: "settings" },
];

const NAV_ICONS = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1"></rect>
      <rect x="14" y="3" width="7" height="7" rx="1"></rect>
      <rect x="3" y="14" width="7" height="7" rx="1"></rect>
      <rect x="14" y="14" width="7" height="7" rx="1"></rect>
    </svg>
  ),
  approvals: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
      <line x1="16" y1="13" x2="8" y2="13"></line>
      <line x1="16" y1="17" x2="8" y2="17"></line>
      <polyline points="10 9 9 9 8 9"></polyline>
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"></circle>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
    </svg>
  ),
};

const KPI_ICONS = {
  total: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
      <line x1="16" y1="13" x2="8" y2="13"></line>
      <line x1="16" y1="17" x2="8" y2="17"></line>
      <polyline points="10 9 9 9 8 9"></polyline>
    </svg>
  ),
  pending: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"></circle>
      <polyline points="12 6 12 12 16 14"></polyline>
    </svg>
  ),
  approved: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
      <polyline points="22 4 12 14.01 9 11.01"></polyline>
    </svg>
  ),
  blocked: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="15" y1="9" x2="9" y2="15"></line>
      <line x1="9" y1="9" x2="15" y2="15"></line>
    </svg>
  ),
};

const STATUSES = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
];

// Progress Ring Component - Circular gauge only
function ProgressRing({ requests }) {
  const stats = useMemo(() => {
    const total = requests.length;
    const approved = requests.filter(r => r.status === "approved").length;
    const pending = requests.filter(r => r.status === "pending").length;
    const rejected = requests.filter(r => r.status === "rejected").length;
    const completionRate = total > 0 ? Math.round((approved / total) * 100) : 0;
    return { total, approved, pending, rejected, completionRate };
  }, [requests]);

  const circumference = 2 * Math.PI * 80; // radius 80
  const offset = circumference - (stats.completionRate / 100) * circumference;

  return (
    <div className="progress-ring-card">
      <div className="progress-ring-header">
        <h2 className="section-title">Approval Rate</h2>
      </div>
      <div className="progress-ring-container">
        <svg className="progress-ring-svg" viewBox="0 0 180 180">
          <defs>
            <linearGradient id="cerulean-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="var(--cerulean-400)" />
              <stop offset="100%" stopColor="var(--cerulean-600)" />
            </linearGradient>
          </defs>
          <circle className="progress-ring-bg" cx="90" cy="90" r="80" />
          <circle
            className="progress-ring-progress"
            cx="90"
            cy="90"
            r="80"
            style={{ strokeDashoffset: offset }}
          />
        </svg>
        <div className="progress-ring-center">
          <div className="progress-ring-value">{stats.completionRate}%</div>
          <div className="progress-ring-label">Approved</div>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard({ email, onLogout }) {
  const [activeNav, setActiveNav] = useState("dashboard");
  const [allRequests, setAllRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showChat, setShowChat] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listApprovals("all");
      setAllRequests(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const counts = useMemo(() => {
    const c = { pending: 0, approved: 0, rejected: 0 };
    for (const r of allRequests) {
      if (c[r.status] !== undefined) c[r.status] += 1;
    }
    return { ...c, total: allRequests.length };
  }, [allRequests]);

  const filteredRequests = useMemo(() => {
    let result = allRequests;
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(r =>
        (r.issue_key || "").toLowerCase().includes(query) ||
        (r.summary || "").toLowerCase().includes(query) ||
        (r.agent_id || "").toLowerCase().includes(query) ||
        (r.project || "").toLowerCase().includes(query)
      );
    }
    if (statusFilter !== "all") {
      result = result.filter(r => r.status === statusFilter);
    }
    return result;
  }, [allRequests, searchQuery, statusFilter]);

  async function handleResolve(id, decision) {
    await resolveApproval(id, decision);
    setAllRequests((prev) =>
      prev.map((r) =>
        (r.issue_key || r.id) === id ? { ...r, status: decision } : r
      )
    );
  }

  const getInitials = (email) => {
    return email
      .split("@")[0]
      .split(".")
      .map((p) => p[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <div className="dashboard-layout">
      {/* Sidebar Navigation */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
              <path d="M2 17l10 5 10-5"></path>
              <path d="M2 12l10 5 10-5"></path>
            </svg>
            <span>Approval Center</span>
          </div>
        </div>
        <nav className="sidebar-nav">
          <div className="nav-section">
            <div className="nav-section-title">Main</div>
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${activeNav === item.id ? "active" : ""}`}
                onClick={() => {
                  setActiveNav(item.id);
                  setSidebarOpen(false);
                }}
              >
                {NAV_ICONS[item.icon]}
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </nav>
        <div className="sidebar-footer">
          <div className="user-profile">
            <div style={{ width: 36, height: 36, borderRadius: "50%", background: "linear-gradient(135deg, var(--cerulean-400), var(--cerulean-500))", display: "flex", alignItems: "center", justifyContent: "center", color: "white", fontWeight: 600, fontSize: "0.875rem" }}>
              {getInitials(email)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {email.split("@")[0]}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Admin</div>
            </div>
            <button className="logout" onClick={onLogout} style={{ padding: "0.375rem 0.75rem", fontSize: "0.75rem" }}>
              Log out
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Top Header */}
        <header className="top-header">
          <div className="header-left">
            <button className="menu-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle menu">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
            <h1 className="page-title">Dashboard</h1>
          </div>
          <div className="search-bar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="search"
              placeholder="Search approvals, projects, agents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search"
            />
          </div>
          <div className="header-right">
            <button className="notification-btn" aria-label="Notifications">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
              </svg>
              <span className="notification-badge" />
            </button>
            <div className="header-avatar">{getInitials(email)}</div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="dashboard-content">
          {error && <div className="error" style={{ marginBottom: "1.5rem", padding: "1rem", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "var(--radius-md)", color: "#ef4444" }}>{error}</div>}
          {loading && allRequests.length === 0 && <p className="empty" style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>Loading…</p>}

          {activeNav === "dashboard" && (
            <>
              {/* KPI Summary Cards */}
              <div className="kpi-grid">
                <div className="kpi-card primary total-requests">
                  <div className="kpi-header">
                    <div className="kpi-icon">{KPI_ICONS.total}</div>
                    <div className="kpi-title">Total Requests</div>
                  </div>
                  <div className="kpi-value centered">{counts.total}</div>
                </div>
                <div className="kpi-card pending-review">
                  <div className="kpi-header">
                    <div className="kpi-icon">{KPI_ICONS.pending}</div>
                    <div className="kpi-title">Pending Review</div>
                  </div>
                  <div className="kpi-value centered" style={{ color: "var(--cerulean-500)" }}>{counts.pending}</div>
                </div>
                <div className="kpi-card approved">
                  <div className="kpi-header">
                    <div className="kpi-icon">{KPI_ICONS.approved}</div>
                    <div className="kpi-title">Approved</div>
                  </div>
                  <div className="kpi-value centered" style={{ color: "#10b981" }}>{counts.approved}</div>
                </div>
                <div className="kpi-card blocked">
                  <div className="kpi-header">
                    <div className="kpi-icon">{KPI_ICONS.blocked}</div>
                    <div className="kpi-title">Rejected</div>
                  </div>
                  <div className="kpi-value centered" style={{ color: "#ef4444" }}>{counts.rejected}</div>
                </div>
              </div>

              {/* Progress Ring Gauge & Agent Request Chart - Side by Side */}
              <div className="dashboard-charts-row">
                <ProgressRing requests={filteredRequests} />
                <AgentRequestChart requests={allRequests} />
              </div>
            </>
          )}

          {activeNav === "approvals" && (
            <div className="approvals-list">
              <div className="section-header">
                <h2 className="section-title">Approvals</h2>
                <div className="section-actions">
                  <select
                    className="status-filter"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    style={{ padding: "0.5rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-primary)" }}
                  >
                    <option value="all">All Statuses</option>
                    <option value="pending">Pending</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </div>
              </div>
              {filteredRequests.length === 0 ? (
                <div className="empty" style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  No approval requests found
                </div>
              ) : (
                <div className="requests-grid">
                  {filteredRequests.map((request) => (
                    <RequestCard
                      key={request.id}
                      request={request}
                      onResolve={handleResolve}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {activeNav === "settings" && (
            <div className="settings-section">
              <div className="section-header">
                <h2 className="section-title">Settings</h2>
              </div>
              <div className="settings-content" style={{ padding: "2rem", background: "var(--surface)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)" }}>
                <h3 style={{ marginBottom: "1.5rem", color: "var(--text-primary)" }}>Account Settings</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", maxWidth: "400px" }}>
                  <div>
                    <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500, color: "var(--text-secondary)" }}>Email</label>
                    <input type="email" value={email} readOnly style={{ width: "100%", padding: "0.75rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500, color: "var(--text-secondary)" }}>Role</label>
                    <input type="text" value="Admin" readOnly style={{ width: "100%", padding: "0.75rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text-primary)" }} />
                  </div>
                  <div>
                    <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500, color: "var(--text-secondary)" }}>Notifications</label>
                    <label style={{ display: "flex", alignItems: "center", gap: "0.75rem", cursor: "pointer" }}>
                      <input type="checkbox" defaultChecked style={{ width: "18px", height: "18px", accentColor: "var(--cerulean-500)" }} />
                      <span style={{ color: "var(--text-primary)" }}>Email notifications for new approval requests</span>
                    </label>
                  </div>
                  <div>
                    <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500, color: "var(--text-secondary)" }}>Theme</label>
                    <select style={{ width: "100%", padding: "0.75rem 1rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-primary)" }}>
                      <option value="system">System Default</option>
                      <option value="light">Light</option>
                      <option value="dark">Dark</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Chat Panel */}
      {showChat && (
        <div className="chat-panel" style={{ position: "fixed", right: "1.5rem", bottom: "1.5rem", width: "380px", maxHeight: "66vh", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", boxShadow: "var(--shadow-xl)", zIndex: 200, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div className="chat-header" style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--surface-2)", borderTopLeftRadius: "var(--radius-xl)", borderTopRightRadius: "var(--radius-xl)" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Approvals Assistant</h3>
            <button className="chat-close" onClick={() => setShowChat(false)} aria-label="Close chat" style={{ padding: "0.5rem", borderRadius: "var(--radius-md)", border: "none", background: "none", color: "var(--text-secondary)", cursor: "pointer" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, minHeight: 0, overflow: "hidden" }}>
            <ChatWidget />
          </div>
        </div>
      )}

      {/* Floating chat toggle button - only show when chat is closed */}
      {!showChat && (
        <button
          className="chat-toggle"
          onClick={() => setShowChat(true)}
          aria-label="Open chat"
          style={{
            position: "fixed",
            bottom: "1.5rem",
            right: "1.5rem",
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            background: "linear-gradient(135deg, var(--cerulean-500), var(--cerulean-600))",
            border: "none",
            color: "white",
            cursor: "pointer",
            boxShadow: "var(--shadow-lg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 150,
            transition: "transform 0.2s ease, box-shadow 0.2s ease"
          }}
          onMouseEnter={(e) => { e.currentTarget.style.transform = "scale(1.05)"; e.currentTarget.style.boxShadow = "var(--shadow-xl)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.boxShadow = "var(--shadow-lg)"; }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </button>
      )}
    </div>
  );
}
