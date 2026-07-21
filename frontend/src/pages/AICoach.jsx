import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PaperPlaneRight, CircleNotch, Sparkle, MagnifyingGlass } from "@phosphor-icons/react";
import { API } from "../api";
import api from "../api";

const SESSION_KEY = "shoehunter_coach_session";

function getSessionId() {
  let s = localStorage.getItem(SESSION_KEY);
  if (!s) {
    s = "coach-" + Math.random().toString(36).slice(2);
    localStorage.setItem(SESSION_KEY, s);
  }
  return s;
}

function splitModels(content) {
  const match = content.match(/\[MODELLER\]:?\s*(.+)/i);
  if (!match) return { text: content, models: [] };
  const text = content.replace(/\[MODELLER\]:?\s*.+/i, "").trimEnd();
  const models = match[1]
    .split("|")
    .map((m) => m.trim())
    .filter((m) => m.length > 2 && m.length < 60);
  return { text, models };
}

const SUGGESTIONS = [
  "Diz ağrısı için asfalt yürüyüşüne uygun, maksimum yastıklamalı ayakkabı öner",
  "97 kg koşucuya dayanıklı koşu ayakkabısı lazım, 6000 TL altı",
  "Taraklı (geniş) ayağa uygun trail ayakkabısı öner",
];

export default function AICoach() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef(null);
  const sessionId = getSessionId();
  const navigate = useNavigate();

  useEffect(() => {
    api.get(`/ai/coach/history/${sessionId}`).then((r) => setMessages(r.data)).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "" }]);
    setStreaming(true);
    try {
      const resp = await fetch(`${API}/ai/coach`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: msg }),
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.delta) {
              setMessages((m) => {
                const copy = [...m];
                copy[copy.length - 1] = {
                  ...copy[copy.length - 1],
                  content: copy[copy.length - 1].content + evt.delta,
                };
                return copy;
              });
            }
          } catch {}
        }
      }
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: "Bağlantı hatası oluştu. Lütfen tekrar deneyin." };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]" data-testid="ai-coach-page">
      <div className="mb-4">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Performans Radarı</div>
        <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">AI Koç</h1>
        <p className="text-zinc-500 text-sm mt-1">İhtiyacınızı anlatın, size uygun modelleri önersin. Profil sayfanızdaki bilgiler dikkate alınır.</p>
      </div>

      <div className="card flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <Sparkle size={36} weight="duotone" className="text-primary mx-auto mb-4" />
              <div className="text-zinc-400 mb-6">Örnek sorular:</div>
              <div className="flex flex-col gap-2 max-w-lg mx-auto">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} data-testid={`coach-suggestion-${i}`} className="btn-secondary text-left !text-xs" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => {
            const { text, models } = m.role === "assistant" ? splitModels(m.content) : { text: m.content, models: [] };
            return (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[75%] rounded-lg px-4 py-3 text-sm whitespace-pre-wrap leading-relaxed ${
                    m.role === "user"
                      ? "bg-primary text-black font-medium"
                      : "bg-zinc-900 border border-zinc-800 text-zinc-200"
                  }`}
                >
                  {text || (streaming && i === messages.length - 1 ? <CircleNotch size={16} className="animate-spin text-primary" /> : "")}
                  {models.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-zinc-800">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-primary font-mono mb-2">
                        Önerilen Modeller — tıkla, mağazalarda ara
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {models.map((model, j) => (
                          <button
                            key={j}
                            data-testid={`coach-model-${i}-${j}`}
                            onClick={() => navigate(`/ai-arama?q=${encodeURIComponent(model)}`)}
                            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full bg-primary/15 text-primary border border-primary/30 hover:bg-primary hover:text-black transition-colors duration-200"
                          >
                            <MagnifyingGlass size={12} weight="bold" />
                            {model}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
        <div className="border-t border-zinc-800 p-4 flex gap-3 bg-black/40 backdrop-blur">
          <input
            data-testid="coach-input"
            className="input-dark"
            placeholder="Örn: 43 numara, asfalt yürüyüşü için maksimum yastıklamalı ayakkabı öner..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            disabled={streaming}
          />
          <button data-testid="coach-send" className="btn-primary shrink-0 flex items-center gap-2" onClick={() => send()} disabled={streaming}>
            {streaming ? <CircleNotch size={16} className="animate-spin" /> : <PaperPlaneRight size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
