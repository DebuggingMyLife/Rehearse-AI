import { useEffect, useRef, useState } from "react";

/** True while the element is in view, for fading in on scroll (and back out when it leaves,
 *  e.g. scrolling back up). */
export function useReveal<T extends Element>(threshold = 0.25) {
  const ref = useRef<T>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(([entry]) => setShown(entry.isIntersecting), { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);

  return { ref, shown };
}
