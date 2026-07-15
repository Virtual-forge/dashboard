// ChatWidget.jsx
// Drop into your dashboard frontend (e.g. src/components/ChatWidget.jsx)
// and render it somewhere in your layout, e.g. <ChatWidget /> in App.jsx.
//
// Talks to POST /api/chat (chatbot.py). Uses the authenticated API client.

import { useState, useRef, useEffect } from "react";
import { request } from "../api.js";

export default function ChatWidget() {
  const [messages, setMessages] = useState([]); // [{role, content}]
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
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
      const data = await request("/api/chat", {
        method: "POST",
        body: JSON.stringify({ messages: nextMessages }),
      });
      setMessages([...nextMessages, { role: "assistant", content: data.reply }]);
    } catch (e) {
      setMessages([
        ...nextMessages,
        { role: "assistant", content: "Something went wrong reaching the chat backend." },
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
    <div className="flex flex-col h-full max-h-[500px] w-full max-w-md border rounded-lg bg-white shadow-sm">
      <div className="px-4 py-3 border-b font-medium text-sm text-gray-700">
        Approvals Assistant
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-sm text-gray-400">
            Try: "show pending approvals" or "approve SCRUM-5"
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm rounded-lg px-3 py-2 max-w-[85%] ${
              m.role === "user"
                ? "bg-blue-600 text-white ml-auto"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="text-sm text-gray-400 italic">thinking...</div>
        )}
        <div ref={scrollRef} />
      </div>

      <div className="flex items-center gap-2 p-3 border-t">
        <input
          className="flex-1 border rounded-md px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about approvals..."
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading}
          className="bg-blue-600 text-white text-sm px-4 py-2 rounded-md disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
