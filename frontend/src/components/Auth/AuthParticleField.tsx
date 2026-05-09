import { useMemo } from "react";

/** Soft floating sparkles for the auth hero (performance-friendly). */
export function AuthParticleField() {
  const dots = useMemo(
    () =>
      Array.from({ length: 40 }, (_, i) => {
        const s = Math.sin(i * 12.9898) * 43758.5453;
        const r = s - Math.floor(s);
        const s2 = Math.cos(i * 4.2 + 1.1) * 8123.4;
        const r2 = s2 - Math.floor(s2);
        return {
          id: i,
          left: 6 + r * 88,
          top: 10 + r2 * 78,
          size: 2 + (i % 4),
          delay: (i % 12) * 0.28,
          duration: 9 + (i % 7) * 1.8,
          hue: i % 3,
        };
      }),
    []
  );

  const bg = (hue: number) =>
    hue === 0 ? "rgba(139,92,246,0.55)" : hue === 1 ? "rgba(236,72,153,0.5)" : "rgba(6,182,212,0.5)";

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {dots.map((d) => (
        <span
          key={d.id}
          className="auth-split-dot absolute rounded-full"
          style={{
            left: `${d.left}%`,
            top: `${d.top}%`,
            width: d.size,
            height: d.size,
            background: bg(d.hue),
            animationDelay: `${d.delay}s`,
            animationDuration: `${d.duration}s`,
          }}
        />
      ))}
    </div>
  );
}
