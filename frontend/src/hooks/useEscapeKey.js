/**
 * useEscapeKey — fires `handler` when the Escape key is pressed.
 * Only attaches the listener while `active` is true, so it's zero-cost
 * when the overlay is closed.
 *
 * Usage:
 *   useEscapeKey(isOpen, () => setOpen(false));
 */
import { useEffect } from "react";

const useEscapeKey = (active, handler) => {
  useEffect(() => {
    if (!active || !handler) return;

    const listener = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        handler(e);
      }
    };

    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [active, handler]);
};

export default useEscapeKey;
