import {
  AnimatePresence,
  motion,
  PanInfo,
  useReducedMotion,
} from "framer-motion";
import {
  ArrowRight,
  Bell,
  Receipt,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AuroraBackground } from "./AuroraBackground";
import { GradientButton } from "./GradientButton";
import { RocketTrail } from "./RocketTrail";
import { ShieldMark } from "./ShieldMark";

const BRAND_EASE = [0.22, 1, 0.36, 1] as const;

export type IntroStoryProps = {
  /** Called when user taps "Get Started ->" on slide 3 (or finishes story). */
  onFinish: () => void;
  /** Called when user taps Skip. */
  onSkip: () => void;
  /** Layout id for the navbar logo morph from /splash. */
  shieldLayoutId?: string;
};

type SlideDef = {
  id: string;
  eyebrow: string;
  title: string;
  body: string;
  visual: (props: { active: boolean }) => JSX.Element;
};

/* ---------- Slide visuals ---------- */

function DonutVisual({ active }: { active: boolean }) {
  const reduce = useReducedMotion();
  // Donut slices (start angle, sweep, color, label)
  const slices = useMemo(
    () => [
      { name: "Food", pct: 28, color: "#7C3AED", icon: "🍱" },
      { name: "Rent", pct: 32, color: "#A855F7", icon: "🏠" },
      { name: "Transport", pct: 14, color: "#EC4899", icon: "🚗" },
      { name: "Subscriptions", pct: 10, color: "#22D3EE", icon: "📺" },
      { name: "Savings", pct: 16, color: "#10B981", icon: "💰" },
    ],
    []
  );

  // Cumulative angles for stroke-dasharray "build" effect
  const C = 2 * Math.PI * 70; // circumference for r=70

  let cumulative = 0;

  // Floating receipts behind donut
  const receipts = useMemo(
    () =>
      [
        { name: "Swiggy", amt: "₹420", left: 4, top: 12 },
        { name: "Netflix", amt: "₹499", left: 78, top: 8 },
        { name: "Uber", amt: "₹186", left: 6, top: 72 },
        { name: "Amazon", amt: "₹2,890", left: 80, top: 70 },
        { name: "Spotify", amt: "₹119", left: 88, top: 38 },
      ],
    []
  );

  return (
    <div className="relative h-full w-full">
      {/* Floating receipts */}
      {receipts.map((r, i) => (
        <motion.div
          key={r.name}
          className="absolute rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-[11px] text-white/85 shadow-[0_8px_30px_rgba(0,0,0,0.35)] backdrop-blur-md"
          style={{ left: `${r.left}%`, top: `${r.top}%` }}
          initial={{ opacity: 0, y: 18 }}
          animate={
            active
              ? {
                  opacity: [0, 1, 0.85],
                  y: reduce ? 0 : [18, -8, -28],
                }
              : { opacity: 0, y: 18 }
          }
          transition={{
            duration: reduce ? 0.4 : 4 + i * 0.4,
            ease: BRAND_EASE,
            delay: 0.2 + i * 0.18,
            repeat: reduce ? 0 : Infinity,
            repeatType: "loop",
          }}
        >
          <div className="flex items-center gap-2">
            <Receipt size={12} className="text-cyan-300" />
            <span className="font-semibold">{r.name}</span>
            <span className="ml-1 text-white/55">{r.amt}</span>
          </div>
        </motion.div>
      ))}

      {/* Donut */}
      <div className="relative mx-auto flex h-full w-full max-w-[420px] items-center justify-center">
        <svg viewBox="0 0 200 200" className="h-[min(74vw,360px)] w-[min(74vw,360px)]">
          <defs>
            {slices.map((s) => (
              <linearGradient key={s.name} id={`donut-${s.name}`} x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor={s.color} stopOpacity="0.85" />
                <stop offset="100%" stopColor={s.color} stopOpacity="1" />
              </linearGradient>
            ))}
          </defs>

          {/* Track */}
          <circle cx="100" cy="100" r="70" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="22" />

          {slices.map((s, i) => {
            const dash = (s.pct / 100) * C;
            const offset = -((cumulative / 100) * C);
            cumulative += s.pct;
            return (
              <motion.circle
                key={s.name}
                cx="100"
                cy="100"
                r="70"
                fill="none"
                stroke={`url(#donut-${s.name})`}
                strokeWidth="22"
                strokeLinecap="butt"
                strokeDasharray={`${dash} ${C - dash}`}
                strokeDashoffset={offset}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={
                  active ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }
                }
                transition={{
                  duration: reduce ? 0.3 : 0.7,
                  ease: BRAND_EASE,
                  delay: 0.1 + i * 0.18,
                }}
                style={{ transform: "rotate(-90deg)", transformOrigin: "100px 100px" }}
              />
            );
          })}

          {/* Center label */}
          <text x="100" y="96" textAnchor="middle" fill="#F5F3FF" fontSize="10" fontFamily="Inter" letterSpacing="2" opacity="0.55">
            THIS MONTH
          </text>
          <text x="100" y="116" textAnchor="middle" fill="#F5F3FF" fontSize="22" fontWeight={700} fontFamily="Space Grotesk">
            ₹48,210
          </text>
        </svg>
      </div>
    </div>
  );
}

function ChatShieldVisual({ active }: { active: boolean }) {
  const reduce = useReducedMotion();
  const fullText = "You spent ₹4,200 more on food this week. Want a budget?";
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!active || reduce) {
      setTyped(active ? fullText : "");
      return;
    }
    setTyped("");
    let i = 0;
    const id = window.setInterval(() => {
      i++;
      setTyped(fullText.slice(0, i));
      if (i >= fullText.length) window.clearInterval(id);
    }, 28);
    return () => window.clearInterval(id);
  }, [active, reduce]);

  return (
    <div className="relative h-full w-full">
      {/* Centered shield with heartbeat */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <ShieldMark stage="complete" size={220} heartbeat={active} />
      </div>

      {/* Typing chat bubble */}
      <motion.div
        className="absolute left-[6%] top-[10%] w-[min(280px,70%)] rounded-2xl border border-white/10 bg-white/[0.07] p-4 text-[13px] text-white/90 shadow-[0_12px_40px_rgba(0,0,0,0.35)] backdrop-blur-xl"
        initial={{ opacity: 0, y: 14, scale: 0.95 }}
        animate={active ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 14, scale: 0.95 }}
        transition={{ duration: 0.55, ease: BRAND_EASE, delay: 0.15 }}
      >
        <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-300">
          <Sparkles size={11} />
          SmartSpend AI
        </div>
        <div className="leading-relaxed">
          {typed}
          <motion.span
            className="ml-0.5 inline-block h-3 w-[2px] -translate-y-[1px] bg-cyan-300 align-middle"
            animate={{ opacity: [1, 0, 1] }}
            transition={{ duration: 0.9, repeat: Infinity }}
          />
        </div>
      </motion.div>

      {/* Notification chip — top right */}
      <motion.div
        className="absolute right-[5%] top-[14%] flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[11px] text-white/80 backdrop-blur-md"
        initial={{ opacity: 0, x: 14 }}
        animate={active ? { opacity: 1, x: 0 } : { opacity: 0, x: 14 }}
        transition={{ duration: 0.55, ease: BRAND_EASE, delay: 0.45 }}
      >
        <Bell size={11} className="text-cyan-300" />
        Hidden fee detected
      </motion.div>
    </div>
  );
}

function RocketGraphVisual({ active }: { active: boolean }) {
  const reduce = useReducedMotion();
  // Curving line graph that the rocket rises along.
  const path = "M 12 180 C 60 160, 90 130, 130 110 S 220 50, 290 22";

  return (
    <div className="relative h-full w-full">
      {/* Soft grid */}
      <svg className="absolute inset-0 h-full w-full opacity-25" viewBox="0 0 320 200" preserveAspectRatio="none" aria-hidden>
        {[40, 80, 120, 160].map((y) => (
          <line key={y} x1="0" y1={y} x2="320" y2={y} stroke="rgba(255,255,255,0.08)" strokeDasharray="2 4" />
        ))}
      </svg>

      <svg viewBox="0 0 320 200" className="relative h-full w-full">
        <defs>
          <linearGradient id="lineGraphGrad" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#22D3EE" />
            <stop offset="60%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#EC4899" />
          </linearGradient>
          <linearGradient id="lineGraphFill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(168,85,247,0.32)" />
            <stop offset="100%" stopColor="rgba(168,85,247,0)" />
          </linearGradient>
        </defs>

        {/* Area fill */}
        <motion.path
          d={`${path} L 290 200 L 12 200 Z`}
          fill="url(#lineGraphFill)"
          initial={{ opacity: 0 }}
          animate={{ opacity: active ? 1 : 0 }}
          transition={{ duration: 0.7, ease: BRAND_EASE, delay: 0.3 }}
        />

        {/* The graph line itself */}
        <motion.path
          d={path}
          fill="none"
          stroke="url(#lineGraphGrad)"
          strokeWidth={3.4}
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: active ? 1 : 0 }}
          transition={{ duration: reduce ? 0.3 : 1.1, ease: BRAND_EASE }}
        />

        {/* Data points */}
        {[
          { cx: 60, cy: 158 },
          { cx: 130, cy: 110 },
          { cx: 220, cy: 56 },
        ].map((p, i) => (
          <motion.circle
            key={`${p.cx}-${p.cy}`}
            cx={p.cx}
            cy={p.cy}
            r={4}
            fill="#F5F3FF"
            stroke="#A855F7"
            strokeWidth={2}
            initial={{ opacity: 0, scale: 0 }}
            animate={active ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0 }}
            transition={{ duration: 0.4, ease: BRAND_EASE, delay: 0.6 + i * 0.15 }}
          />
        ))}
      </svg>

      {/* Rocket flying along the curve */}
      <div className="pointer-events-none absolute inset-0">
        <RocketTrail launch={active} pathD={path} className="h-full w-full" />
      </div>

      {/* Sparkles */}
      {!reduce &&
        active &&
        [
          { left: 26, top: 30 },
          { left: 60, top: 16 },
          { left: 78, top: 40 },
        ].map((p, i) => (
          <motion.div
            key={`${p.left}-${p.top}`}
            className="absolute h-1.5 w-1.5 rounded-full bg-white shadow-[0_0_10px_rgba(255,255,255,0.7)]"
            style={{ left: `${p.left}%`, top: `${p.top}%` }}
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 0] }}
            transition={{ duration: 1.6, repeat: Infinity, delay: 0.8 + i * 0.3, ease: BRAND_EASE }}
          />
        ))}
    </div>
  );
}

/* ---------- Main story component ---------- */

export function IntroStory({ onFinish, onSkip, shieldLayoutId = "ssShieldMark" }: IntroStoryProps) {
  const reduce = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);

  const slides = useMemo<SlideDef[]>(
    () => [
      {
        id: "see",
        eyebrow: "01 — Visibility",
        title: "See every rupee.",
        body: "Track every transaction across all your accounts in one calm view.",
        visual: ({ active }) => <DonutVisual active={active} />,
      },
      {
        id: "ai",
        eyebrow: "02 — Intelligence",
        title: "AI that watches your back.",
        body: "On-device AI flags fraud, overspends and hidden fees in real time.",
        visual: ({ active }) => <ChatShieldVisual active={active} />,
      },
      {
        id: "grow",
        eyebrow: "03 — Growth",
        title: "Grow, save, invest — on autopilot.",
        body: "Round-ups, smart goals and AI investing — all running quietly in the background.",
        visual: ({ active }) => <RocketGraphVisual active={active} />,
      },
    ],
    []
  );

  const next = useCallback(() => {
    if (index >= slides.length - 1) {
      onFinish();
      return;
    }
    setDirection(1);
    setIndex((i) => Math.min(slides.length - 1, i + 1));
  }, [index, slides.length, onFinish]);

  const prev = useCallback(() => {
    if (index <= 0) return;
    setDirection(-1);
    setIndex((i) => Math.max(0, i - 1));
  }, [index]);

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "Enter") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "Escape") onSkip();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, onSkip]);

  const onDragEnd = (_e: unknown, info: PanInfo) => {
    const SWIPE = 70;
    if (info.offset.x < -SWIPE) next();
    else if (info.offset.x > SWIPE) prev();
  };

  const slide = slides[index];
  const isLast = index === slides.length - 1;

  // Slide + parallax variants
  const variants = {
    enter: (dir: number) => ({ x: dir * 60, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir: number) => ({ x: -dir * 60, opacity: 0 }),
  };

  // Background shifts at 0.4x parallax of the index change.
  const parallaxX = `${index * -16}%`;

  return (
    <div className="relative flex min-h-[100dvh] w-full flex-col overflow-hidden bg-[#070418] font-sans text-ss-ink">
      {/* Parallax background */}
      <motion.div
        className="absolute inset-0 -z-10"
        animate={{ x: reduce ? "0%" : parallaxX }}
        transition={{ duration: 0.8, ease: BRAND_EASE }}
      >
        <AuroraBackground starCount={50} tone={index === 1 ? "warm" : "default"} />
      </motion.div>

      {/* Top navbar with morphing shield */}
      <header className="relative z-10 flex items-center justify-between px-5 pt-5 md:px-10 md:pt-7">
        <div className="flex items-center gap-2.5">
          <ShieldMark layoutId={shieldLayoutId} stage="complete" size={36} />
          <span className="font-heading text-base font-semibold tracking-tight text-white">
            SmartSpend
          </span>
        </div>
        <button
          type="button"
          onClick={onSkip}
          className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-white/65 transition hover:border-white/25 hover:bg-white/[0.08] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
        >
          Skip
        </button>
      </header>

      {/* Slide stage (drag-to-swipe on mobile, arrows on desktop) */}
      <motion.div
        className="relative z-10 flex flex-1 items-center justify-center px-5 pb-32 pt-8 md:px-12 md:pb-28 md:pt-10"
        drag="x"
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.18}
        onDragEnd={onDragEnd}
      >
        <AnimatePresence custom={direction} mode="wait">
          <motion.div
            key={slide.id}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.55, ease: BRAND_EASE }}
            className="grid w-full max-w-6xl grid-cols-1 items-center gap-10 lg:grid-cols-2 lg:gap-14"
          >
            {/* Visual column (top on mobile, left on desktop) */}
            <div className="relative h-[52vw] max-h-[420px] min-h-[260px] w-full lg:order-2 lg:h-[460px]">
              <slide.visual active={true} />
            </div>

            {/* Copy column */}
            <div className="lg:order-1">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-300/90">
                {slide.eyebrow}
              </p>
              <h2 className="font-heading text-[clamp(2rem,6vw,3.5rem)] font-semibold leading-[1.05] tracking-tight text-white">
                <span className="bg-ss-brand bg-[length:200%_200%] bg-clip-text text-transparent">
                  {slide.title}
                </span>
              </h2>
              <p className="mt-5 max-w-[32ch] text-[clamp(0.95rem,2.2vw,1.125rem)] leading-relaxed text-ss-mute">
                {slide.body}
              </p>

              {/* Inline CTA on last slide */}
              {isLast ? (
                <div className="mt-8">
                  <GradientButton
                    onClick={onFinish}
                    trailingIcon={<ArrowRight size={18} />}
                    className="!rounded-full"
                  >
                    Get Started
                  </GradientButton>
                  <p className="mt-3 text-xs text-white/40">
                    No card required. 60-second sign up.
                  </p>
                </div>
              ) : (
                <div className="mt-8 hidden items-center gap-2 text-xs uppercase tracking-[0.2em] text-white/40 lg:flex">
                  <TrendingUp size={14} className="text-cyan-300" />
                  Swipe / use arrow keys to continue
                </div>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </motion.div>

      {/* Bottom bar: dots + next. The single Skip control lives in the top-right
          header — we intentionally do NOT render a second Skip here. The grid
          guarantees the dots stay perfectly centered even when the Next button
          widens to "Get Started" on slide 03. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 px-5 pb-7 md:px-10 md:pb-10">
        <div className="pointer-events-auto mx-auto grid max-w-6xl grid-cols-[1fr_auto_1fr] items-center gap-4">
          {/* Left spacer — mirrors the Next column to keep dots math-centered */}
          <div aria-hidden />

          {/* Dots */}
          <div className="flex items-center justify-center gap-2">
            {slides.map((s, i) => (
              <button
                key={s.id}
                type="button"
                aria-label={`Go to slide ${i + 1}`}
                onClick={() => {
                  setDirection(i > index ? 1 : -1);
                  setIndex(i);
                }}
                className="group relative h-2.5 rounded-full transition-all duration-500 ease-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
                style={{ width: i === index ? 32 : 10 }}
              >
                <span
                  className={`block h-full w-full rounded-full transition-all duration-500 ease-brand ${
                    i === index ? "bg-ss-brand" : "bg-white/20 group-hover:bg-white/35"
                  }`}
                />
              </button>
            ))}
          </div>

          {/* Next — right-aligned within its column so it never pushes the dots */}
          <div className="flex justify-end">
            <GradientButton
              onClick={next}
              size="md"
              trailingIcon={<ArrowRight size={16} />}
              className="!min-h-[48px] !px-5"
            >
              {isLast ? "Get Started" : "Next"}
            </GradientButton>
          </div>
        </div>
      </div>
    </div>
  );
}

export default IntroStory;
