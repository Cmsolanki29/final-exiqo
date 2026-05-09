import { useEffect, useState } from "react";

/**
 * Animates from 0 toward `target` over `duration` ms (ease-out).
 * Works for currency and integers; format in the component.
 */
export const useCountUp = (target, duration = 1000) => {
  const t = Number(target);
  const safe = Number.isFinite(t) ? t : 0;
  const [count, setCount] = useState(0);

  useEffect(() => {
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - (1 - p) * (1 - p);
      setCount(safe * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
      else setCount(safe);
    };
    setCount(0);
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [safe, duration]);

  return count;
};
