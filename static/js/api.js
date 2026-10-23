// Thin wrapper around fetch for the expense API (same origin, so relative URLs).
// Every function either resolves with parsed JSON or throws an Error whose
// message is safe to show the user.

const FALLBACK_MESSAGE = "Something went wrong";
const NETWORK_MESSAGE = "Network error. Check your connection.";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    // fetch only rejects when the request never got a response.
    throw new Error(NETWORK_MESSAGE);
  }

  if (response.status === 204) return null;

  // Error bodies look like {"error": "..."}; tolerate non-JSON bodies too.
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(body?.error || FALLBACK_MESSAGE);
    error.status = response.status;
    throw error;
  }
  return body;
}

// Builds "?a=1&b=2", skipping empty values (the API ignores them anyway).
function toQuery(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export function listExpenses({ category, page, limit }) {
  return request(`/expenses${toQuery({ category, page, limit })}`);
}

export function createExpense(expense) {
  return request("/expenses", { method: "POST", body: JSON.stringify(expense) });
}

export function deleteExpense(id) {
  return request(`/expenses/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function getSummary(month) {
  return request(`/expenses/summary${toQuery({ month })}`);
}
