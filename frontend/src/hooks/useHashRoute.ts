import { useEffect, useState } from "react";

export type Route =
  | { page: "setup" }
  | { page: "cv"; sessionId: string }
  | { page: "questions"; sessionId: string }
  | { page: "attempt"; sessionId: string; questionId: number };

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "s" && parts[1] && parts[2] === "q" && /^\d+$/.test(parts[3] ?? "")) {
    return { page: "attempt", sessionId: parts[1], questionId: Number(parts[3]) };
  }
  if (parts[0] === "s" && parts[1]) {
    return parts[2] === "cv" ? { page: "cv", sessionId: parts[1] } : { page: "questions", sessionId: parts[1] };
  }
  return { page: "setup" };
}

export function navigate(path: string) {
  window.location.hash = path;
}

/** Tiny hash router, so a refresh keeps you on the same session. */
export function useHashRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
