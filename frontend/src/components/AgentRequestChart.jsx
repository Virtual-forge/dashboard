import { useMemo } from "react";

const SEGMENTS = [
  { key: "pending", className: "seg-pending" },
  { key: "approved", className: "seg-approved" },
  { key: "rejected", className: "seg-rejected" },
];

export default function AgentRequestChart({ requests }) {
  const agents = useMemo(() => {
    const byAgent = new Map();
    for (const r of requests) {
      const name = r.agent_id || "Unknown agent";
      if (!byAgent.has(name)) {
        byAgent.set(name, { name, pending: 0, approved: 0, rejected: 0, total: 0 });
      }
      const entry = byAgent.get(name);
      if (entry[r.status] !== undefined) entry[r.status] += 1;
      entry.total += 1;
    }
    return [...byAgent.values()].sort((a, b) => b.total - a.total);
  }, [requests]);

  if (agents.length === 0) {
    return null;
  }

  const maxTotal = agents[0].total;

  return (
    <section className="agent-chart">
      <div className="agent-chart-head">
        <h2>Requests by agent</h2>
        <div className="agent-chart-legend">
          <span className="legend-item">
            <span className="legend-swatch seg-pending" /> Pending
          </span>
          <span className="legend-item">
            <span className="legend-swatch seg-approved" /> Approved
          </span>
          <span className="legend-item">
            <span className="legend-swatch seg-rejected" /> Blocked
          </span>
        </div>
      </div>

      <div className="agent-chart-rows">
        {agents.map((a) => (
          <div key={a.name} className="agent-chart-row">
            <span className="agent-chart-name">{a.name}</span>
            <div className="agent-chart-bar-track">
              <div
                className="agent-chart-bar"
                style={{ width: `${(a.total / maxTotal) * 100}%` }}
              >
                {SEGMENTS.map((s) =>
                  a[s.key] > 0 ? (
                    <span
                      key={s.key}
                      className={`agent-chart-segment ${s.className}`}
                      style={{ width: `${(a[s.key] / a.total) * 100}%` }}
                      title={`${s.key}: ${a[s.key]}`}
                    />
                  ) : null
                )}
              </div>
            </div>
            <span className="agent-chart-total">{a.total}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
