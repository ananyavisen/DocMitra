import { useState } from "react";
import { Bot, Send, X, MessageCircle, LoaderCircle } from "lucide-react";
import "./Chatbot.css";

const API_URL = import.meta.env.VITE_CHAT_API_URL || "http://127.0.0.1:8000/api/chat/";

export default function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! I'm DocMitra AI. Ask me about your application documents or requirements." }
  ]);
  const [loading, setLoading] = useState(false);

  async function sendMessage(event) {
    event.preventDefault();
    const message = input.trim();
    if (!message || loading) return;

    setMessages(prev => [...prev, { role: "user", text: message }]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const answer = data.answer ?? data.response;
      if (typeof answer !== "string") throw new Error("Unexpected response format");
      setMessages(prev => [...prev, { role: "assistant", text: answer }]);
    } catch (error) {
      console.error("DocMitra chatbot request failed:", error);
      setMessages(prev => [...prev, {
        role: "assistant",
        text: "I couldn't reach the server. Check that Django is running and update VITE_CHAT_API_URL to the correct chat endpoint."
      }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatbot-widget">
      {isOpen && <section className="chat-window">
        <header className="chat-header">
          <div className="chat-brand-icon"><Bot size={22} /></div>
          <div className="chat-brand"><strong>DocMitra AI</strong><span>Application assistant</span></div>
          <button className="chat-close" onClick={() => setIsOpen(false)} aria-label="Close chat"><X size={20} /></button>
        </header>
        <div className="chat-messages" aria-live="polite">
          {messages.map((item, index) => <div key={index} className={`chat-message ${item.role}`}>
            {item.role === "assistant" && <Bot size={16} className="message-icon" />}
            <p>{item.text}</p>
          </div>)}
          {loading && <div className="chat-loading"><LoaderCircle size={17} className="chat-spinner" /> DocMitra is thinking…</div>}
        </div>
        <form className="chat-input-area" onSubmit={sendMessage}>
          <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about your documents…" aria-label="Message DocMitra AI" disabled={loading} />
          <button type="submit" disabled={loading || !input.trim()} aria-label="Send message"><Send size={18} /></button>
        </form>
        <p className="chat-disclaimer">Verify important requirements against official notices.</p>
      </section>}
      <button className="chat-launcher" onClick={() => setIsOpen(v => !v)} aria-label={isOpen ? "Close chatbot" : "Open chatbot"}>
        {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
        {!isOpen && <span>Ask DocMitra</span>}
      </button>
    </div>
  );
}