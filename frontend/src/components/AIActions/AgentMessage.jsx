import React from "react";
import { Sparkles } from "lucide-react";
import ToolCallTimeline from "./ToolCallTimeline";
import ItineraryCard from "./ItineraryCard";

const fmt = (ts) =>
  ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

function renderMarkdownLite(text) {
  if (!text) return null;
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="text-white">{part.slice(2, -2)}</strong>;
    }
    return part.split("\n").map((line, j, arr) => (
      <span key={`${i}-${j}`}>
        {line}
        {j < arr.length - 1 && <br />}
      </span>
    ));
  });
}

export default function AgentMessage({
  content,
  steps,
  plan,
  streaming,
  timestamp,
}) {
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

        {content?.trim() ? (
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
            {renderMarkdownLite(content)}
            {streaming ? (
              <span
                aria-hidden
                style={{
                  display: "inline-block",
                  width: 2,
                  height: "1em",
                  background: "#A78BFA",
                  marginLeft: 3,
                  verticalAlign: "text-bottom",
                  borderRadius: 1,
                  animation: "tp-cursor-blink 0.65s step-end infinite",
                }}
              />
            ) : null}
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
