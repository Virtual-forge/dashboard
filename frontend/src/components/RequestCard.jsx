import { useState } from "react";

export default function RequestCard({ request, onResolve }) {
  const [busy, setBusy] = useState(false);

  async function handle(decision) {
    setBusy(true);
    try {
      await onResolve(request.id, decision);
    } finally {
      setBusy(false);
    }
  }

  const isPending = request.status === "pending";

  return (
    <div className={`card status-${request.status}`}>
      <div className="card-header">
        <span className="tool-name">{request.tool_name}</span>
        <span className={`badge badge-${request.status}`}>{request.status}</span>
      </div>

      {request.context && <p className="context">{request.context}</p>}

      <pre className="args">{JSON.stringify(request.tool_args, null, 2)}</pre>

      <div className="meta">
        {request.requested_by && <span>Requested by {request.requested_by}</span>}
        {request.agent_name && <span>Agent: {request.agent_name}</span>}
        <span>{new Date(request.created_at).toLocaleString()}</span>
      </div>

      {!isPending && request.resolved_by && (
        <div className="meta resolved">
          {request.status === "approved" ? "Approved" : "Blocked"} by{" "}
          {request.resolved_by}
          {request.resolved_at &&
            ` on ${new Date(request.resolved_at).toLocaleString()}`}
        </div>
      )}

      {isPending && (
        <div className="actions">
          <button
            className="approve"
            disabled={busy}
            onClick={() => handle("approved")}
          >
            Approve
          </button>
          <button
            className="block"
            disabled={busy}
            onClick={() => handle("rejected")}
          >
            Block
          </button>
        </div>
      )}
    </div>
  );
}
