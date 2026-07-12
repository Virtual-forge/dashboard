const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function getToken() {
  return localStorage.getItem("token");
}

async function request(path, options = {}) {
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
  return request(`/api/approvals?status=${encodeURIComponent(status)}`);
}

export function resolveApproval(id, decision) {
  return request(`/api/approvals/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });
}
