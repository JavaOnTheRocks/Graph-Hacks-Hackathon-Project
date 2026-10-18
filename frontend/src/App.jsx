
import { useEffect, useState } from "react";
import {
  MessageSquare,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";

import {
  sendChatMessage,
  getConversations,
  getConversation,
  deleteConversation,
} from "./services/api";

import "./index.css";

const USER_ID = "demo-user";

function createChat(number) {
  return {
    id: crypto.randomUUID(),
    title: `Thread_${number}`,
    messages: [],
    isPersisted: false,
    created_at: new Date().toISOString(),
  };
}

function getNextThreadNumber(chats) {
  return (
    chats.reduce((max, chat) => {
      const match = chat.title?.match(/^Thread_(\d+)$/);
      return match ? Math.max(max, Number(match[1])) : max;
    }, 0) + 1
  );
}

function normalizeConversation(conversation) {
  return {
    id: conversation.thread_id,
    title: conversation.title || "New chat",
    messages: [],
    isPersisted: true,
    created_at: conversation.created_at,
    updated_at: conversation.updated_at,
    message_count: Number(conversation.message_count || 0),
  };
}

function normalizeMessages(messages) {
  return messages.map((message) => ({
    role: message.role,
    content: message.content,
  }));
}

export default function App() {
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [input, setInput] = useState("");
  const [loadingChats, setLoadingChats] = useState({});
  const [errorChats, setErrorChats] = useState({});
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");

  // Load conversation metadata from PostgreSQL through the backend.
  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      setHistoryLoading(true);
      setHistoryError("");

      try {
        const result = await getConversations(USER_ID);
        const conversations = (result.conversations || []).map(
          normalizeConversation
        );

        if (cancelled) return;

        setChats(conversations);

        if (conversations.length > 0) {
          const firstChat = conversations[0];
          setActiveChatId(firstChat.id);

          try {
            const detail = await getConversation(
              USER_ID,
              firstChat.id
            );

            if (cancelled) return;

            setChats((previous) =>
              previous.map((chat) =>
                chat.id === firstChat.id
                  ? {
                      ...chat,
                      messages: normalizeMessages(
                        detail.messages || []
                      ),
                      title:
                        detail.conversation?.title || chat.title,
                    }
                  : chat
              )
            );
          } catch (error) {
            if (!cancelled) {
              setErrorChats((previous) => ({
                ...previous,
                [firstChat.id]:
                  error.message || "Could not load this conversation.",
              }));
            }
          }
        } else {
          setActiveChatId(null);
        }
      } catch (error) {
        if (!cancelled) {
          setHistoryError(
            error.message || "Could not load conversation history."
          );
        }
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, []);

  const activeChat = chats.find(
    (chat) => chat.id === activeChatId
  );

  const loading = Boolean(
    activeChatId && loadingChats[activeChatId]
  );

  const error = activeChatId
    ? errorChats[activeChatId] || ""
    : "";

  function newChat() {
    const chat = createChat(getNextThreadNumber(chats));

    setChats((previous) => [chat, ...previous]);
    setActiveChatId(chat.id);
    setInput("");
    setHistoryError("");
  }

  function updateChat(chatId, updater) {
    setChats((previous) =>
      previous.map((chat) =>
        chat.id === chatId ? updater(chat) : chat
      )
    );
  }

  async function selectChat(chat) {
    setActiveChatId(chat.id);
    setInput("");
    setHistoryError("");

    if (!chat.isPersisted) return;

    // Avoid fetching the same history repeatedly.
    if (chat.messages.length > 0) return;

    setErrorChats((previous) => ({
      ...previous,
      [chat.id]: "",
    }));

    try {
      const result = await getConversation(USER_ID, chat.id);

      updateChat(chat.id, (current) => ({
        ...current,
        title: result.conversation?.title || current.title,
        messages: normalizeMessages(result.messages || []),
      }));
    } catch (error) {
      setErrorChats((previous) => ({
        ...previous,
        [chat.id]:
          error.message || "Could not load this conversation.",
      }));
    }
  }

  async function refreshHistory() {
    const result = await getConversations(USER_ID);
    const serverChats = (result.conversations || []).map(
      normalizeConversation
    );

    setChats((previous) => {
      // Keep unsent draft conversations in the sidebar.
      const drafts = previous.filter((chat) => !chat.isPersisted);
      return [...drafts, ...serverChats];
    });
  }

  async function handleSend(event) {
    event?.preventDefault();

    const message = input.trim();
    if (!message) return;

    let chat = activeChat;

    if (!chat) {
      chat = createChat(getNextThreadNumber(chats));
      setChats((previous) => [chat, ...previous]);
      setActiveChatId(chat.id);
    }

    const chatId = chat.id;

    if (loadingChats[chatId]) return;

    updateChat(chatId, (current) => ({
      ...current,
      messages: [
        ...current.messages,
        { role: "user", content: message },
      ],
    }));

    setInput("");
    setErrorChats((previous) => ({
      ...previous,
      [chatId]: "",
    }));
    setLoadingChats((previous) => ({
      ...previous,
      [chatId]: true,
    }));

    try {
      const result = await sendChatMessage({
        userId: USER_ID,
        threadId: chatId,
        message,
      });

      updateChat(chatId, (current) => ({
        ...current,
        isPersisted: true,
        title:
          current.isPersisted
            ? current.title
            : message.replace(/\s+/g, " ").slice(0, 60),
        messages: [
          ...current.messages,
          {
            role: "assistant",
            content: result.answer ?? "No response was returned.",
          },
        ],
      }));

      // Refresh metadata so the sidebar reflects the database.
      try {
        await refreshHistory();
      } catch (refreshError) {
        console.error("Could not refresh conversation list:", refreshError);
      }
    } catch (error) {
      setErrorChats((previous) => ({
        ...previous,
        [chatId]:
          error.message || "Unable to connect to the assistant.",
      }));

      // The backend may have saved the user message before failing.
      // Reload the saved history when the conversation already exists.
      try {
        const detail = await getConversation(USER_ID, chatId);

        updateChat(chatId, (current) => ({
          ...current,
          isPersisted: true,
          messages: normalizeMessages(detail.messages || []),
        }));

        await refreshHistory();
      } catch {
        // A brand-new failed request may not have created a conversation.
      }
    } finally {
      setLoadingChats((previous) => ({
        ...previous,
        [chatId]: false,
      }));
    }
  }

  async function deleteChat(event, chatId) {
    event.stopPropagation();

    const chatToDelete = chats.find((chat) => chat.id === chatId);
    if (!chatToDelete) return;

    if (chatToDelete.isPersisted) {
      try {
        await deleteConversation(USER_ID, chatId);
      } catch (error) {
        setErrorChats((previous) => ({
          ...previous,
          [chatId]:
            error.message || "Could not delete this conversation.",
        }));
        return;
      }
    }

    const remaining = chats.filter((chat) => chat.id !== chatId);

    setChats(remaining);

    setLoadingChats((previous) => {
      const updated = { ...previous };
      delete updated[chatId];
      return updated;
    });

    setErrorChats((previous) => {
      const updated = { ...previous };
      delete updated[chatId];
      return updated;
    });

    if (activeChatId === chatId) {
      const nextChat = remaining[0];

      setActiveChatId(nextChat?.id ?? null);
      setInput("");

      if (nextChat?.isPersisted) {
        await selectChat(nextChat);
      }
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Sparkles size={21} />
          </div>
          <span>Personal Assistant</span>
        </div>

        <button className="new-chat" onClick={newChat}>
          <Plus size={18} /> New chat
        </button>

        <div className="sidebar-label">YOUR CONVERSATIONS</div>

        <div className="conversation-list">
          {historyLoading && (
            <p className="empty-chats">Loading conversation history...</p>
          )}

          {!historyLoading && historyError && (
            <p className="error-message">{historyError}</p>
          )}

          {!historyLoading && !historyError && chats.length === 0 && (
            <p className="empty-chats">
              Your conversations will appear here.
            </p>
          )}

          {chats.map((chat) => (
            <div
              key={chat.id}
              className={`conversation-item ${
                chat.id === activeChatId ? "selected" : ""
              }`}
            >
              <button
                className="conversation-select"
                onClick={() => selectChat(chat)}
                title={chat.title}
              >
                <MessageSquare size={15} />
                <span>{chat.title}</span>
                {loadingChats[chat.id] && (
                  <span className="thread-loading-dot">...</span>
                )}
              </button>

              <button
                className="delete-chat"
                onClick={(event) => deleteChat(event, chat.id)}
                title="Delete conversation"
                aria-label={`Delete ${chat.title}`}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          Your personal space for thinking, planning and research.
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <div className="topbar-title">
              {activeChat?.title || "Assistant"}
            </div>
            <div className="connection">
              <span className="status-dot" /> AI workspace
            </div>
          </div>
          <div className="avatar">PA</div>
        </header>

        <section className="chat-area">
          {!activeChat || activeChat.messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">
                <Sparkles size={25} />
              </div>
              <h1>How can I help you today?</h1>
              <p>
                Ask a question, research a topic, or plan your next move.
              </p>

              <div className="suggestions">
                <button onClick={() => setInput("Help me plan my week")}>
                  <span>01</span>
                  <div>
                    <strong>Plan my week</strong>
                    <small>Organize tasks and priorities</small>
                  </div>
                </button>

                <button
                  onClick={() => setInput("Research the latest AI trends")}
                >
                  <span>02</span>
                  <div>
                    <strong>Research a topic</strong>
                    <small>Explore ideas and information</small>
                  </div>
                </button>

                <button
                  onClick={() => setInput("Help me learn a new skill")}
                >
                  <span>03</span>
                  <div>
                    <strong>Learn something</strong>
                    <small>Break a goal into clear steps</small>
                  </div>
                </button>
              </div>
            </div>
          ) : (
            <div className="message-list">
              {activeChat.messages.map((message, index) => (
                <div
                  className={`message-row ${message.role}`}
                  key={`${activeChat.id}-${index}`}
                >
                  {message.role === "assistant" && (
                    <div className="message-avatar">
                      <Sparkles size={16} />
                    </div>
                  )}

                  <div className="message-content">
                    <div className="message-author">
                      {message.role === "user" ? "You" : "Assistant"}
                    </div>
                    <div className="message-text">{message.content}</div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="loading-text">
                  Assistant is thinking in {activeChat.title}...
                </div>
              )}
            </div>
          )}
        </section>

        <div className="composer-wrap">
          {error && <div className="error-message">{error}</div>}

          <form className="composer" onSubmit={handleSend}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Message your assistant..."
              rows={2}
            />

            <div className="composer-bottom">
              <span>Enter to send · Shift + Enter for a new line</span>
              <button
                className="send-button"
                type="submit"
                disabled={!input.trim() || loading}
              >
                {loading ? "..." : "Send"}
              </button>
            </div>
          </form>

          <p className="disclaimer">
            AI can make mistakes. Verify important information.
          </p>
        </div>
      </main>
    </div>
  );
}
