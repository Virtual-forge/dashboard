import { useState } from "react";

export default function RequestCard({ request, onResolve }) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  async function handle(e, decision) {
    e.stopPropagation(); // don't toggle the dropdown when clicking a button
    setBusy(true);
    try {
      await onResolve(request.id, decision);
    } finally {
      setBusy(false);
    }
  }

  const isPending = request.status === "pending";

  return (
    <div className={`row status-${request.status} ${open ? "open" : ""}`}>
      <button
        type="button"
        className="row-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="chevron">▶</span>

        <span className="row-summary">
          <span className="row-summary-top">
            <span className="tool-name">{request.tool_name}</span>
            <span className={`badge badge-${request.status}`}>{request.status}</span>
            {request.requested_by && (
              <span className="row-requester">by {request.requested_by}</span>
            )}
          </span>
          {request.tool_description && (
            <span className="tool-description">{request.tool_description}</span>
          )}
        </span>

        <span className="row-actions">
          {isPending ? (
            <>
              <button
                type="button"
                className="approve"
                disabled={busy}
                onClick={(e) => handle(e, "approved")}
              >
                Approve
              </button>
              <button
                type="button"
                className="block"
                disabled={busy}
                onClick={(e) => handle(e, "rejected")}
              >
                Block
              </button>
            </>
          ) : (
            <span className="resolved-by">
              {request.status === "approved" ? "Approved" : "Blocked"} by{" "}
              {request.resolved_by || "—"}
            </span>
          )}
        </span>
      </button>

      {open && (
        <div className="row-details">
          {request.tool_description && (
            <p className="tool-description-full">{request.tool_description}</p>
          )}
          {request.context && <p className="context">{request.context}</p>}

          <pre className="args">{JSON.stringify(request.tool_args, null, 2)}</pre>

          <div className="meta">
            {request.requested_by && <span>Requested by {request.requested_by}</span>}
            {request.agent_id && <span>Agent: {request.agent_id}</span>}
            {request.run_id && <span>Run: {request.run_id}</span>}
            <span>Created {new Date(request.created_at).toLocaleString()}</span>
          </div>

          {!isPending && request.resolved_by && (
            <div className="meta resolved">
              {request.status === "approved" ? "Approved" : "Blocked"} by{" "}
              {request.resolved_by}
              {request.resolved_at &&
                ` on ${new Date(request.resolved_at).toLocaleString()}`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
