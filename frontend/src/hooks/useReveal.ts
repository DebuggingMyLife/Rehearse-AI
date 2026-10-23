import { useEffect, useRef, useState } from "react";

/** True once the element has scrolled into view (stays true), for fade-in-on-scroll. */
export function useReveal<T extends Element>(threshold = 0.25) {
  const ref = useRef<T>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || shown) return;
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [shown, threshold]);

  return { ref, shown };
}
