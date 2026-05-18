import React from "react";
import { Sparkles } from "lucide-react";
import ToolCallTimeline from "./ToolCallTimeline";
import ItineraryCard from "./ItineraryCard";
import { renderMarkdownLite, TypewriterText } from "../common/TypewriterText";

const fmt = (ts) =>
  ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

function TypingIndicator() {
  return (
    <div
      data-testid="agent-typing-indicator"
      className="flex items-center gap-2.5 px-1 py-1"
      aria-label="Trip Planner is typing"
    >
      <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-white/[0.07] border-l-[3px] border-l-violet-500/55 bg-white/[0.04] px-3.5 py-2.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-violet-400/80"
            style={{
              animation: `tp-dot-blink 1.2s ${i * 0.2}s infinite ease-in-out`,
            }}
          />
        ))}
      </div>
      <span className="select-none text-[11px] italic text-white/40">
        Trip Planner is typing…
      </span>
    </div>
  );
}

export default function AgentMessage({
  content,
  steps,
  plan,
  streaming,
  timestamp,
}) {
  const hasContent = Boolean((content || "").trim());
  const showBubble = hasContent || streaming;

  return (
    <div
      className="mb-4 flex items-start gap-2.5"
      style={{ animation: "tp-fade-up 0.22s ease-out both" }}
    >
      <div
        className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full text-white"
        style={{
          background:
            "linear-gradient(135deg,#7C3AED 0%,#6d28d9 45%,#2563eb 100%)",
          boxShadow: "0 0 22px rgba(124,58,237,0.35)",
        }}
        aria-hidden
      >
        <Sparkles className="h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1">
        <ToolCallTimeline steps={steps} />

        {showBubble ? (
          <div
            className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed text-gray-200"
            style={{
              background: "rgba(255,255,255,0.04)",
              borderTop: "1px solid rgba(255,255,255,0.07)",
              borderRight: "1px solid rgba(255,255,255,0.07)",
              borderBottom: "1px solid rgba(255,255,255,0.07)",
              borderLeft: "3px solid rgba(139,92,246,0.55)",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {streaming ? (
              hasContent ? (
                <TypewriterText
                  key={`tw-${timestamp}`}
                  text={content}
                  isStreaming={streaming}
                />
              ) : (
                <TypingIndicator />
              )
            ) : (
              renderMarkdownLite(content)
            )}
          </div>
        ) : null}

        {plan ? <ItineraryCard plan={plan} /> : null}

        <span className="mt-0.5 ml-1 block text-[10px] text-white/30">
          {fmt(timestamp)}
        </span>
      </div>
    </div>
  );
}
