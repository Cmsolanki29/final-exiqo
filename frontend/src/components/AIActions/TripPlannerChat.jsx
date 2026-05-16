import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Plane, RotateCcw } from "lucide-react";
import { TOKEN_ACCESS_KEY } from "../../services/api";
import UserMessage from "./UserMessage";
import AgentMessage from "./AgentMessage";
import SuggestedPrompts from "./SuggestedPrompts";

/**
 * Premium chat surface for the Trip Planner.
 * Streams SSE events from /api/ai-actions/trip-planner/chat and live-renders:
 *   • tool_start / tool_end → SmartSpend Engine + Live Intelligence timelines
 *   • delta                 → typewriter answer
 *   • final                 → structured PLAN_JSON → ItineraryCard
 */
export default function TripPlannerChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [providers, setProviders] = useState(null);
  const [error, setError] = useState("");

  const abortRef = useRef(null);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  // ── Auth header (matches the existing AI chat pattern) ──────────────────
  const authHeaders = () => {
    const t = (() => {
      try {
        return localStorage.getItem(TOKEN_ACCESS_KEY) || "";
      } catch {
        return "";
      }
    })();
    return t ? { Authorization: `Bearer ${t}` } : {};
  };

  // ── Capability probe (drives small status dots in header) ───────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/ai-actions/trip-planner/health", {
          headers: authHeaders(),
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) {
          const base = data?.providers || {};
          setProviders({
            ...base,
            travel_engine: Boolean(data?.mcp_connected),
          });
        }
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Auto-scroll ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (messages.length === 0) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  // ── Auto-resize textarea ────────────────────────────────────────────────
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [input]);

  // ── History payload for the backend (last 10 turns of plain text) ───────
  const historyForBackend = useMemo(
    () =>
      messages
        .filter((m) => (m.role === "user" || m.role === "assistant") && (m.content || "").trim())
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content })),
    [messages]
  );

  const stopActive = useCallback(() => {
    try {
      abortRef.current?.abort();
    } catch {
      /* ignore */
    }
    abortRef.current = null;
  }, []);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = (text || "").trim();
      if (!trimmed || loading) return;
      setError("");

      const ts = Date.now();
      const agentId = `agent-${ts}`;

      setMessages((prev) => [
        ...prev,
        { id: `user-${ts}`, role: "user", content: trimmed, timestamp: ts },
        {
          id: agentId,
          role: "assistant",
          content: "",
          steps: [],
          plan: null,
          streaming: true,
          timestamp: ts + 1,
        },
      ]);
      setLoading(true);
      setInput("");

      const ctrl = new AbortController();
      abortRef.current = ctrl;
      let firstChunk = false;

      try {
        const res = await fetch("/api/ai-actions/trip-planner/chat", {
          method: "POST",
          headers: { ...authHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed, history: historyForBackend }),
          signal: ctrl.signal,
        });

        if (!res.ok) {
          let detail = "";
          try {
            const j = await res.json();
            detail = j?.detail || "";
          } catch {
            /* ignore */
          }
          throw new Error(detail || `HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let sep;
          while ((sep = buf.indexOf("\n\n")) >= 0) {
            const block = buf.slice(0, sep).trim();
            buf = buf.slice(sep + 2);
            for (const line of block.split("\n")) {
              if (!line.startsWith("data: ")) continue;
              try {
                const evt = JSON.parse(line.slice(6).trim());
                firstChunk = true;
                handleEvent(agentId, evt);
              } catch {
                /* skip malformed */
              }
            }
          }
        }
      } catch (err) {
        if (err?.name === "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentId
                ? { ...m, streaming: false, content: m.content || "Stopped." }
                : m
            )
          );
        } else {
          const msg = err?.message || "Network error";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentId
                ? {
                    ...m,
                    streaming: false,
                    content: `Sorry — I couldn't reach the Travel Engine. (${msg})`,
                  }
                : m
            )
          );
          setError(msg);
        }
      } finally {
        if (!firstChunk) {
          setMessages((prev) =>
            prev.map((m) => (m.id === agentId ? { ...m, streaming: false } : m))
          );
        }
        abortRef.current = null;
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loading, historyForBackend]
  );

  const handleEvent = useCallback((agentId, evt) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== agentId) return m;
        const steps = Array.isArray(m.steps) ? [...m.steps] : [];

        if (evt.type === "tool_start") {
          steps.push({
            id: `${evt.tool}-${steps.length}`,
            tool: evt.tool,
            friendly: evt.friendly,
            status: "running",
            source: evt.source || "direct",
          });
          return { ...m, steps };
        }
        if (evt.type === "tool_end") {
          for (let i = steps.length - 1; i >= 0; i--) {
            if (steps[i].tool === evt.tool && steps[i].status === "running") {
              steps[i] = {
                ...steps[i],
                status: "done",
                summary: evt.summary,
                ok: evt.ok,
                source: evt.source || steps[i].source || "direct",
              };
              break;
            }
          }
          return { ...m, steps };
        }
        if (evt.type === "delta") {
          return { ...m, content: (m.content || "") + (evt.text || "") };
        }
        if (evt.type === "final") {
          return {
            ...m,
            content: evt.text || m.content || "",
            plan: evt.plan || null,
            streaming: false,
          };
        }
        if (evt.type === "error") {
          return {
            ...m,
            streaming: false,
            content:
              evt.message ||
              "Sorry — the Travel Engine is unavailable right now. Please try again.",
          };
        }
        return m;
      })
    );
  }, []);

  const handleSubmit = (e) => {
    e?.preventDefault?.();
    sendMessage(input);
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const handleClear = () => {
    stopActive();
    setMessages([]);
    setError("");
    setInput("");
  };

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-gradient-to-br from-[#15102A] to-[#0F0A1F] shadow-[0_18px_60px_rgba(124,58,237,0.18)]">
      {/* Local keyframes scoped via style tag — keeps the component self-contained */}
      <style>{`
        @keyframes tp-fade-up {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes tp-cursor-blink {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0; }
        }
        @keyframes tp-dot-blink {
          0%, 100% { opacity: 0.25; transform: translateY(0); }
          50% { opacity: 1; transform: translateY(-2px); }
        }
      `}</style>

      {/* ── Header ── */}
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] bg-white/[0.025] px-4 py-3">
        <div className="flex items-center gap-3">
          <div
            className="grid h-10 w-10 place-items-center rounded-xl text-white shadow-[0_0_24px_rgba(124,58,237,0.4)]"
            style={{
              background: "linear-gradient(135deg,#7C3AED 0%,#A855F7 50%,#22D3EE 100%)",
            }}
          >
            <Plane className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="font-heading text-sm font-semibold text-white">
              Trip Planner · <span className="text-cyan-300">Travel Engine</span>
            </p>
            <p className="text-[11px] text-gray-400">
              Personalised, financially-aware itineraries powered by Live Intelligence.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {providers ? (
            <ProviderDots providers={providers} />
          ) : null}
          {messages.length > 0 ? (
            <button
              type="button"
              onClick={handleClear}
              className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-[11px] text-white/50 transition hover:border-white/20 hover:text-white"
            >
              <RotateCcw className="h-3 w-3" /> Reset
            </button>
          ) : null}
        </div>
      </div>

      {/* ── Messages ── */}
      <div
        className="overflow-y-auto px-4 py-4 scrollbar-thin scrollbar-thumb-white/10"
        style={{ minHeight: 420, maxHeight: "min(70vh, 720px)" }}
      >
        {messages.length === 0 && !loading ? (
          <EmptyState onPick={(p) => sendMessage(p)} disabled={loading} />
        ) : null}

        {messages.map((m) =>
          m.role === "user" ? (
            <UserMessage key={m.id} content={m.content} timestamp={m.timestamp} />
          ) : (
            <AgentMessage
              key={m.id}
              content={m.content}
              steps={m.steps}
              plan={m.plan}
              streaming={!!m.streaming}
              timestamp={m.timestamp}
            />
          )
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Error banner (optional) ── */}
      {error ? (
        <div className="mx-4 mb-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      ) : null}

      {/* ── Composer ── */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-white/[0.06] bg-white/[0.02] px-4 py-3"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-white/[0.08] bg-white/[0.03] px-3 py-2 focus-within:border-violet-500/40 focus-within:ring-2 focus-within:ring-violet-500/20">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Where do you want to go? e.g. Plan a Kashmir trip for 5 days"
            disabled={loading}
            className="flex-1 resize-none bg-transparent text-sm text-white placeholder:text-gray-500 focus:outline-none disabled:opacity-50"
            style={{ maxHeight: 140 }}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-white transition disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: "linear-gradient(135deg,#7C3AED 0%,#6d28d9 45%,#2563eb 100%)",
              boxShadow: input.trim() && !loading ? "0 0 18px rgba(124,58,237,0.5)" : "none",
            }}
            aria-label="Send message"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-[10px] text-gray-500">
          Trip Planner uses your real SmartSpend finances to verdict GREEN / YELLOW / RED. Numbers reflect live providers when configured.
        </p>
      </form>
    </div>
  );
}

function ProviderDots({ providers }) {
  const items = [
    { key: "openai", label: "AI" },
    { key: "weather", label: "Weather" },
    { key: "flights", label: "Flights" },
    { key: "hotels", label: "Hotels" },
    { key: "places", label: "Places" },
    { key: "travel_engine", label: "Travel" },
  ];
  return (
    <div className="hidden items-center gap-2 sm:flex">
      {items.map((it) => (
        <span
          key={it.key}
          title={`${it.label}: ${providers?.[it.key] ? "live" : "estimate"}`}
          className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] text-gray-400"
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: providers?.[it.key] ? "#10B981" : "#64748B" }}
            aria-hidden
          />
          {it.label}
        </span>
      ))}
    </div>
  );
}

function EmptyState({ onPick, disabled }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 px-4 py-10 text-center">
      <div
        className="grid h-14 w-14 place-items-center rounded-2xl text-white shadow-[0_0_30px_rgba(124,58,237,0.5)]"
        style={{
          background: "linear-gradient(135deg,#7C3AED 0%,#A855F7 50%,#22D3EE 100%)",
        }}
      >
        <Plane className="h-6 w-6" />
      </div>
      <div>
        <h3 className="font-heading text-lg font-semibold text-white">
          Where to next?
        </h3>
        <p className="mt-1 text-sm text-gray-400">
          Ask me to plan a trip and I'll cross-check your savings, EMIs, and the weather before
          recommending dates and a budget.
        </p>
      </div>
      <div className="mx-auto max-w-xl">
        <SuggestedPrompts onSelect={onPick} disabled={disabled} />
      </div>
    </div>
  );
}
