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
const AGENT_ID = "approval-demo"; // must match the id= in jira_agent.py's AgentOS(...)

// Polling config for waiting on a paused (needs-approval) run to complete.
const POLL_INTERVAL_MS = 5000; // check every 5s
const POLL_MAX_ATTEMPTS = 60; // ~5 minutes total -- tune to your approval SLA

export default function ChatWidget() {
  const [messages, setMessages] = useState([]); // [{role, content}]
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [waitingOnApproval, setWaitingOnApproval] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const scrollRef = useRef(null);

  // Guards against a stale poll loop touching state after unmount,
  // and lets us cancel an in-flight poll if the component goes away.
  const pollCancelRef = useRef(false);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => {
      pollCancelRef.current = true;
    };
  }, []);

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
      if (sessionId) {
        body.set("session_id", sessionId); // keep conversation context across turns
      }
      body.append("user_id", "hamzalakehayli@gmail.com"); // static email for now

      const res = await fetch(`${AGENT_OS_URL}/agents/${AGENT_ID}/runs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "ngrok-skip-browser-warning": "true",
        },
        body: body.toString(),
      });

      if (!res.ok) {
        throw new Error(`AgentOS returned ${res.status}`);
      }

      const data = await res.json();
      const responseSessionId = data.session_id || sessionId;
      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id);
      }
      setMessages((prev) => [...prev, { role: "assistant", content: data.content }]);

      const status = (data.status || "").toUpperCase();

      if (status === "PAUSED") {
        // Tool call needs approval (Jira). The approval happens out-of-band
        // (Jira automation hits /continue on the backend directly), so we
        // poll here until the run is no longer paused, then show the final
        // assistant message.
        setWaitingOnApproval(true);
        pollCancelRef.current = false;
        pollForCompletion(data.run_id, responseSessionId);
        return; // keep `loading` true -- pollForCompletion clears it when done
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Couldn't reach the agent at ${AGENT_OS_URL}. Is jira_agent.py running?`,
        },
      ]);
      setLoading(false);
    }
  }

  async function pollForCompletion(runId, effectiveSessionId) {
    for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));

      if (pollCancelRef.current) return; // component unmounted, stop

      try {
        const res = await fetch(
          `${AGENT_OS_URL}/sessions/${effectiveSessionId}/runs/${runId}`,
          { headers: { "ngrok-skip-browser-warning": "true" } }
        );

        if (!res.ok) continue; // transient error, keep polling

        const data = await res.json();
        const status = (data.status || "").toUpperCase();

        if (status && status !== "PAUSED") {
          // Run finished (completed, failed, whatever terminal state) --
          // show the result and stop polling.
          setMessages((prev) => [...prev, { role: "assistant", content: data.content }]);
          setWaitingOnApproval(false);
          setLoading(false);
          return;
        }
        // still PAUSED -- keep waiting
      } catch (e) {
        // network hiccup -- keep trying
      }
    }

    // Gave up after POLL_MAX_ATTEMPTS
    setWaitingOnApproval(false);
    setLoading(false);
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "Still waiting on approval -- check back later or refresh once it's approved.",
      },
    ]);
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
              {waitingOnApproval && (
                <span className="waiting-label"> Waiting on approval…</span>
              )}
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
