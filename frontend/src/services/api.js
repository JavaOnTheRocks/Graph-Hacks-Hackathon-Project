
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(
      `Request failed (${response.status}): ${details}`
    );
  }

  return response.json();
}

export async function sendChatMessage({
  userId,
  threadId,
  message,
}) {
  return apiRequest("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      thread_id: threadId,
      message,
    }),
  });
}

export async function getConversations(userId) {
  const params = new URLSearchParams({
    user_id: userId,
  });

  return apiRequest(
    `/api/v1/conversations?${params.toString()}`
  );
}

export async function getConversation(userId, threadId) {
  const params = new URLSearchParams({
    user_id: userId,
  });

  return apiRequest(
    `/api/v1/conversations/${encodeURIComponent(threadId)}?${params.toString()}`
  );
}

export async function deleteConversation(userId, threadId) {
  const params = new URLSearchParams({
    user_id: userId,
  });

  return apiRequest(
    `/api/v1/conversations/${encodeURIComponent(threadId)}?${params.toString()}`,
    {
      method: "DELETE",
    }
  );
}
