/**
 * useCountUp — animate a number from 0 → target with ease-out.
 * Returns the current display value. Respects prefers-reduced-motion.
 *
 *   const n = useCountUp(284612, { duration: 800 });
 *   <span>{Math.round(n).toLocaleString()}</span>
 */
import { useEffect, useRef, useState } from "react";

export type UseCountUpOptions = {
  /** Animation duration in ms. Default 800. */
  duration?: number;
  /** Reset to 0 and re-animate when target changes. Default true. */
  resetOnTargetChange?: boolean;
};

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

const prefersReducedMotion =
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useCountUp(target: number, options: UseCountUpOptions = {}): number {
  const { duration = 800, resetOnTargetChange = true } = options;
  const [value, setValue] = useState<number>(prefersReducedMotion ? target : 0);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const fromRef = useRef<number>(0);

  useEffect(() => {
    if (prefersReducedMotion || !Number.isFinite(target)) {
      setValue(target);
      return;
    }

    fromRef.current = resetOnTargetChange ? 0 : value;
    startTimeRef.current = null;

    const tick = (now: number) => {
      if (startTimeRef.current == null) startTimeRef.current = now;
      const elapsed = now - startTimeRef.current;
      const t = Math.min(1, elapsed / duration);
      const eased = easeOutCubic(t);
      setValue(fromRef.current + (target - fromRef.current) * eased);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration, resetOnTargetChange]);

  return value;
}

export default useCountUp;
