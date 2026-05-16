import React from "react";

const fmt = (ts) =>
  ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

export default function UserMessage({ content, timestamp }) {
  return (
    <div
      className="mb-3 flex justify-end"
      style={{ animation: "tp-fade-up 0.22s ease-out both" }}
    >
      <div className="flex max-w-[80%] flex-col items-end gap-0.5">
        <div
          className="rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed text-white"
          style={{ background: "linear-gradient(135deg,#6d28d9,#4f46e5)" }}
        >
          {content}
        </div>
        <span className="pr-1 text-[10px] text-white/30">{fmt(timestamp)}</span>
      </div>
    </div>
  );
}
