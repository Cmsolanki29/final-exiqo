import { motion, useReducedMotion } from "framer-motion";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export type GradientButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
  size?: "md" | "lg";
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  full?: boolean;
};

const sizeMap = {
  md: "min-h-[48px] px-5 text-[15px]",
  lg: "min-h-[56px] px-7 text-base",
};

/**
 * Brand-grade button primitive.
 * - Primary: brand gradient, glow + lift on hover, shimmering sweep.
 * - Ghost: glass outline that glows on hover.
 *
 * Always >= 48px tall (mobile-friendly), focus-visible cyan ring.
 */
export function GradientButton({
  children,
  variant = "primary",
  size = "lg",
  leadingIcon,
  trailingIcon,
  full,
  className,
  disabled,
  ...rest
}: GradientButtonProps) {
  const reduce = useReducedMotion();

  const base = `group relative inline-flex items-center justify-center gap-2.5 overflow-hidden rounded-2xl font-semibold tracking-tight transition-all duration-500 ease-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#070418] disabled:cursor-not-allowed disabled:opacity-55 ${sizeMap[size]} ${full ? "w-full" : ""}`;

  if (variant === "ghost") {
    return (
      <motion.button
        type="button"
        {...(rest as Record<string, unknown>)}
        disabled={disabled}
        whileHover={reduce || disabled ? undefined : { y: -1 }}
        whileTap={reduce || disabled ? undefined : { scale: 0.97 }}
        className={`${base} border border-white/15 bg-white/[0.04] text-ss-ink/95 backdrop-blur-xl hover:border-white/25 hover:bg-white/[0.07] hover:shadow-[0_0_28px_rgba(124,58,237,0.18)] ${className ?? ""}`}
      >
        {leadingIcon ? <span className="relative">{leadingIcon}</span> : null}
        <span className="relative">{children}</span>
        {trailingIcon ? <span className="relative">{trailingIcon}</span> : null}
      </motion.button>
    );
  }

  return (
    <motion.button
      type="button"
      {...(rest as Record<string, unknown>)}
      disabled={disabled}
      whileHover={reduce || disabled ? undefined : { y: -2 }}
      whileTap={reduce || disabled ? undefined : { scale: 0.97 }}
      transition={{ type: "spring", stiffness: 380, damping: 24 }}
      className={`${base} bg-ss-brand bg-[length:220%_220%] text-white shadow-ss-cta hover:shadow-ss-cta-hover ${className ?? ""}`}
      style={{ backgroundPosition: "0% 50%" }}
    >
      {/* Shimmer sweep */}
      <span
        className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent opacity-0 transition duration-700 ease-brand group-hover:translate-x-full group-hover:opacity-100"
        aria-hidden
      />
      {/* Subtle inner highlight */}
      <span
        className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/15 to-transparent mix-blend-overlay"
        aria-hidden
      />
      {leadingIcon ? <span className="relative">{leadingIcon}</span> : null}
      <span className="relative">{children}</span>
      {trailingIcon ? <span className="relative">{trailingIcon}</span> : null}
    </motion.button>
  );
}

export default GradientButton;
