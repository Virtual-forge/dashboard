// ChatWidget.jsx
// Talks DIRECTLY to the AgentOS server (jira_agent.py, its own port --
// default 7777), NOT through the dashboard backend. This is a separate
// origin from your dashboard backend, so jira_agent.py's AgentOS must have
// this origin in cors_allowed_origins or the browser will block it.
//
// This is intentionally unauthenticated at the AgentOS level right now --
// see the README note on locking this down before any real deployment.

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

const AGENT_OS_URL = import.meta.env.VITE_AGENT_OS_URL || "http://localhost:7777";
const AGENT_ID = "jira-approval-agent"; // must match the id= in jira_agent.py's AgentOS(...)

export default function ChatWidget() {
  const [messages, setMessages] = useState([]); // [{role, content}]
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    const nextMessages = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);

    try {
      // AgentOS run endpoints take form-encoded input, not JSON.
      const body = new URLSearchParams();
      body.set("message", text);
      body.set("stream", "false");
      body.set("session_id", sessionId); // keeps conversation context across turns

      const res = await fetch(`${AGENT_OS_URL}/agents/${AGENT_ID}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });

      if (!res.ok) {
        throw new Error(`AgentOS returned ${res.status}`);
      }

      const data = await res.json();
      setMessages([...nextMessages, { role: "assistant", content: data.content }]);
    } catch (e) {
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: `Couldn't reach the agent at ${AGENT_OS_URL}. Is jira_agent.py running?`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="chat-widget">
      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="empty">Try: "show pending approvals" or "approve SCRUM-5"</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-message ${m.role}`}>
            <div className="chat-bubble">
              {m.role === "assistant" ? (
                <ReactMarkdown>{m.content}</ReactMarkdown>
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant loading">
            <div className="chat-bubble">
              <span className="spinner" aria-label="Generating response" />
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-row">
          <input
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about approvals..."
            disabled={loading}
          />
          <button className="chat-send" onClick={send} disabled={loading}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
