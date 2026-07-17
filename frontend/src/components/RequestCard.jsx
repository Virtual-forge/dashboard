import { useState } from "react";

export default function RequestCard({ request, onResolve }) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  async function handle(e, decision) {
    e.stopPropagation(); // don't toggle the dropdown when clicking a button
    setBusy(true);
    try {
      await onResolve(request.issue_key || request.id, decision);
    } finally {
      setBusy(false);
    }
  }

  const isPending = request.status === "pending";

  return (
    <div className={`row status-${request.status} ${open ? "open" : ""}`}>
      <div
        className="row-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen((o) => !o); } }}
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
      </div>

      {open && (
        <div className="row-details">
          <dl className="details-list">
            {request.tool_description && (
              <>
                <dt>Description</dt>
                <dd>{request.tool_description}</dd>
              </>
            )}
            <dt>Tool name</dt>
            <dd className="tool-name-detail">{request.tool_name}</dd>

            {request.agent_id && (
              <>
                <dt>Agent name</dt>
                <dd>{request.agent_id}</dd>
              </>
            )}

            <dt>Args</dt>
            <dd>
              <pre className="args">{JSON.stringify(request.tool_args, null, 2)}</pre>
            </dd>
          </dl>

          {request.context && <p className="context">{request.context}</p>}

          <div className="meta">
            {request.requested_by && <span>Requested by {request.requested_by}</span>}
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
