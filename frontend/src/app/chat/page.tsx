"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, BookOpenText, FileText, Plus, Quote, Sparkles, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { API_URL, api, Citation, DocumentRecord } from "@/lib/api";
import { PageHeading } from "@/components/PageHeading";

type ChatMessage = { role: "user" | "assistant"; content: string; citations?: Citation[] };

export default function ChatPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api<DocumentRecord[]>("/documents").then(setDocuments).catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load sources")).finally(() => setLoadingSources(false)); }, []);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [messages, busy]);

  async function send(event?: FormEvent, suggested?: string) {
    event?.preventDefault();
    const content = (suggested ?? question).trim();
    if (!content || busy) return;
    setQuestion(""); setError(""); setBusy(true);
    setMessages((current) => [...current, { role: "user", content }]);
    try {
      const token = localStorage.getItem("vanco.access_token");
      const response = await fetch(`${API_URL}/chat/completions/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ message: content, conversation_id: conversationId }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail ?? `Request failed (${response.status})`);
      }
      if (!response.body) throw new Error("Streaming is unavailable in this browser");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completed = false;
      const applyAssistant = (delta: string, citations?: Citation[]) => {
        setMessages((current) => {
          const last = current[current.length - 1];
          if (last?.role === "assistant") {
            return [...current.slice(0, -1), { ...last, content: delta ? last.content + delta : last.content, ...(citations ? { citations } : {}) }];
          }
          return [...current, { role: "assistant", content: delta, ...(citations ? { citations } : {}) }];
        });
      };
      while (true) {
        const result = await reader.read();
        buffer += decoder.decode(result.value, { stream: !result.done });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const data = frame.split(/\r?\n/).filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
          if (!data) continue;
          const event = JSON.parse(data) as { type: string; content?: string; message?: string; answer?: string; conversation_id?: string; citations?: Citation[] };
          if (event.type === "delta" && event.content) applyAssistant(event.content);
          if (event.type === "error") throw new Error(event.message ?? "Unable to complete this question");
          if (event.type === "done") {
            completed = true;
            setConversationId(event.conversation_id);
            applyAssistant("", event.citations ?? []);
          }
        }
        if (result.done) break;
      }
      if (!completed) throw new Error("The response stream ended before completion");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to answer this question"); }
    finally { setBusy(false); }
  }

  function startNew() { setMessages([]); setConversationId(undefined); setError(""); }

  const suggestions = ["What are the key points in my documents?", "Find any deadlines or dates", "Compare the main recommendations"];

  return <>
    <PageHeading eyebrow="ASK YOUR SOURCES" title="Workspace chat" description="A grounded conversation across your indexed documents." action={<button className="secondary-button new-chat-button" onClick={startNew}><Plus size={16} /> New conversation</button>} />
    {!loadingSources && documents.filter((document) => document.status === "COMPLETED").length === 0 && <div className="chat-source-notice"><BookOpenText size={17} /><span><strong>{error ? "Sources could not be loaded." : "No indexed sources yet."}</strong> {error ? "Check the connection, then reload this view." : "Add documents first, then ask questions across them."}</span></div>}
    <section className="chat-workspace">
      <div className="chat-main">
        <div className={`conversation ${messages.length ? "conversation-active" : ""}`}>
          {messages.length === 0 ? <div className="chat-welcome"><span className="chat-welcome-icon"><Sparkles size={19} /></span><p className="eyebrow">DOCUMENT INTELLIGENCE</p><h2>What do you need<br />to know?</h2><p className="chat-welcome-description">Ask a question. Answers are grounded in your sources and linked back to the page they came from.</p><div className="suggestion-list">{suggestions.map((suggestion, index) => <button key={suggestion} onClick={() => void send(undefined, suggestion)}><span>0{index + 1}</span>{suggestion}<ArrowUp size={14} /></button>)}</div></div> : <div className="message-list">{messages.map((message, index) => <article key={`${index}-${message.role}`} className={`chat-message message-${message.role}`}><span className={`message-avatar ${message.role === "assistant" ? "vanco-message-avatar" : "user-message-avatar"}`}>{message.role === "assistant" ? <Sparkles size={15} /> : "Y"}</span><div className="message-body"><span className="message-author">{message.role === "assistant" ? "Vanco" : "You"}</span><div className="markdown-content"><ReactMarkdown>{message.content}</ReactMarkdown></div>{message.citations && message.citations.length > 0 && <div className="citation-list"><span className="citation-heading"><Quote size={12} /> SOURCES</span>{message.citations.map((citation, citationIndex) => <button key={`${citation.document_id}-${citation.page_number}-${citationIndex}`} className="citation-chip" onClick={() => setSelectedCitation(citation)}><FileText size={13} /><span>{citation.filename}</span><small>p. {citation.page_number}</small></button>)}</div>}</div></article>)}{busy && <article className="chat-message message-assistant"><span className="message-avatar vanco-message-avatar"><Sparkles size={15} /></span><div className="typing-indicator"><i /><i /><i /></div></article>}{error && <div className="chat-error">{error}</div>}<div ref={endRef} /></div>}
        </div>
        <form className="chat-composer" onSubmit={(event) => void send(event)}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} placeholder="Ask a question about your documents…" rows={2} maxLength={12000} aria-label="Your question" /><div className="composer-footer"><span><span className="composer-lock" /> Grounded in {documents.filter((document) => document.status === "COMPLETED").length} indexed sources</span><button aria-label="Send question" className="send-button" type="submit" disabled={busy || !question.trim()}><ArrowUp size={18} /></button></div></form>
      </div>
      <aside className="source-rail"><div className="rail-heading"><div><p className="eyebrow">CONTEXT</p><h3>Your sources</h3></div><span className="rail-count">{loadingSources ? "…" : documents.length}</span></div><p className="rail-description">Answers are searched across the documents below.</p><div className="rail-documents" aria-busy={loadingSources}>{loadingSources ? <div className="rail-empty">Checking connected sources…</div> : documents.length ? documents.map((document) => <div className="rail-document" key={document.id}><span className="rail-file-icon"><FileText size={15} /></span><div><strong>{document.filename}</strong><small>{document.status === "COMPLETED" ? "Indexed and searchable" : document.status.toLowerCase()}</small></div><span className={`rail-status rail-${document.status.toLowerCase()}`} /></div>) : <div className="rail-empty">Your uploaded documents will appear here.</div>}</div><div className="rail-footer"><span><span />PRIVATE CONTEXT</span><small>Only your documents are searched.</small></div></aside>
    </section>
    {selectedCitation && <div className="drawer-scrim" onClick={() => setSelectedCitation(null)}><aside className="citation-drawer" onClick={(event) => event.stopPropagation()}><div className="drawer-heading"><div><p className="eyebrow">SOURCE EXCERPT</p><h2>Page {selectedCitation.page_number}</h2></div><button className="icon-button" aria-label="Close source viewer" onClick={() => setSelectedCitation(null)}><X size={19} /></button></div><div className="drawer-document"><FileText size={16} /><span>{selectedCitation.filename}</span></div><blockquote>{selectedCitation.snippet_text}</blockquote><div className="drawer-footer"><span className="drawer-source-label"><Quote size={13} /> CITED IN ANSWER</span><span className="drawer-lock">PRIVATE SOURCE</span></div></aside></div>}
  </>;
}
