const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function getToken() {
  return localStorage.getItem("token");
}

export async function request(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (res.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    window.location.reload();
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  return res.json();
}

export async function login(email, password) {
  const data = await request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("token", data.token);
  localStorage.setItem("email", data.email);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("email");
}

export function getStoredEmail() {
  return localStorage.getItem("email");
}

export function isLoggedIn() {
  return Boolean(getToken());
}
function parseApprovalDescription(description = "") {
  const get = (label) => {
    const match = description.match(new RegExp(`${label}:\\s*([^\\n]+)`));
    return match ? match[1].trim() : null;
  };

  const getJsonBlock = (label) => {
    const match = description.match(
      new RegExp(`${label}:\\s*\`\`\`([\\s\\S]*?)\`\`\``)
    );
    if (!match) return null;
    try {
      return JSON.parse(match[1].trim());
    } catch {
      return null;
    }
  };

  return {
    agent: get("Agent"),
    run_id: get("Run"),
    session_id: get("Session"),
    requested_by: get("Requested by \\(user_id\\)"),
    tool: get("Tool"),
    context: getJsonBlock("Context"),
    requirements: getJsonBlock("Requirements"),
    tool_args: getJsonBlock("Arguments"),
  };
}

export function listApprovals(status = "pending") {
  return request(`/api/jira/approvals?status=${encodeURIComponent(status)}`).then(data => {
    return data.approvals.map(issue => {
      const parsed = parseApprovalDescription(issue.description);
      return {
        id: issue.issue_key,
        issue_key: issue.issue_key,
        tool_name: issue.tool_name,
        tool_description: issue.tool_description,
        status: issue.status?.toLowerCase() || 'pending',
        requested_by: parsed.requested_by || issue.assignee,
        agent_id: issue.agent_id,
        tool_args: parsed.tool_args || {},
        context: parsed.context,
        run_id: parsed.run_id || issue.approval_id,
        resolved_by: null,
        approval_type: issue.approval_type,
        session_id: parsed.session_id,
        tool: parsed.tool,
        created_at: issue.created,
        requirements: parsed.requirements,
      };
    });
  });
}
export function resolveApproval(issueKey, decision) {
  return request(`/api/jira/approvals/${issueKey}/resolve`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}
