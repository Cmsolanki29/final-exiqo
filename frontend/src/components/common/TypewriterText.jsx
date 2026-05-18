import { useEffect, useRef, useState } from "react";

/** Minimal markdown: **bold** and newlines only. */
export function renderMarkdownLite(text) {
  if (!text) return null;
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part.split("\n").map((line, j, arr) => (
      <span key={`${i}-${j}`}>
        {line}
        {j < arr.length - 1 && <br />}
      </span>
    ));
  });
}

/**
 * ChatGPT-style typewriter: reveals `text` progressively while `isStreaming`,
 * with a blinking cursor until caught up (or stream ends).
 */
export function TypewriterText({
  text,
  isStreaming,
  charDelayMs = 12,
  cursorClassName = "",
}) {
  const [pos, setPos] = useState(0);
  const textRef = useRef(text);

  useEffect(() => {
    textRef.current = text;
  }, [text]);

  useEffect(() => {
    const id = setInterval(() => {
      setPos((p) => (p >= textRef.current.length ? p : p + 1));
    }, charDelayMs);
    return () => clearInterval(id);
  }, [charDelayMs]);

  useEffect(() => {
    if (!isStreaming) setPos(textRef.current.length);
  }, [isStreaming]);

  const displayed = text.slice(0, pos);
  const showCursor = isStreaming || pos < text.length;

  return (
    <>
      <style>{`
        @keyframes tw-cursor-blink {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0; }
        }
      `}</style>
      <span data-testid="typewriter-text">
        {renderMarkdownLite(displayed)}
        {showCursor ? (
          <span
            data-testid="typewriter-cursor"
            aria-hidden
            className={cursorClassName}
            style={{
              display: "inline-block",
              width: 2,
              height: "1em",
              background: "#a78bfa",
              marginLeft: 3,
              verticalAlign: "text-bottom",
              borderRadius: 1,
              animation: "tw-cursor-blink 0.65s step-end infinite",
            }}
          />
        ) : null}
      </span>
    </>
  );
}
