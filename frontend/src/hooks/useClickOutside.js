/**
 * useClickOutside — fires `handler` when a mousedown lands outside `ref`.
 * Pass multiple refs to exclude several elements (e.g. trigger + panel).
 *
 * Usage:
 *   useClickOutside([panelRef, triggerRef], () => setOpen(false));
 */
import { useEffect } from "react";

const useClickOutside = (refs, handler) => {
  useEffect(() => {
    if (!handler) return;
    const refList = Array.isArray(refs) ? refs : [refs];

    const listener = (e) => {
      const clickedInside = refList.some((r) => r.current?.contains(e.target));
      if (!clickedInside) handler(e);
    };

    document.addEventListener("mousedown", listener);
    return () => document.removeEventListener("mousedown", listener);
  }, [refs, handler]);
};

export default useClickOutside;
