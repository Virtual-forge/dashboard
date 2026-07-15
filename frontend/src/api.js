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

export function listApprovals(status = "pending") {
  return request(`/api/jira/approvals?status=${encodeURIComponent(status)}`).then(data => {
    // Transform Jira response to match frontend expectations
    return data.approvals.map(issue => ({
      id: issue.issue_key,  // Use issue_key as the identifier
      issue_key: issue.issue_key,
      tool_name: issue.tool_name,
      tool_description: issue.tool_name, // Jira doesn't have description, use tool_name
      status: issue.status?.toLowerCase() || 'pending',
      requested_by: issue.assignee,
      agent_id: issue.agent_id,
      tool_args: {}, // Jira doesn't have tool_args in the simplified response
      context: null,
      run_id: issue.approval_id, // Use approval_id as run_id reference
      resolved_by: null,
      approval_type: issue.approval_type,
    }));
  });
}

export function resolveApproval(issueKey, decision) {
  return request(`/api/jira/approvals/${issueKey}/resolve`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}
