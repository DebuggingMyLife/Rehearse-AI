import { useEffect, useState } from "react";

export type Route =
  | { page: "landing" }
  | { page: "setup" }
  | { page: "build" }
  | { page: "buildStep"; buildId: string }
  | { page: "cv"; sessionId: string }
  | { page: "questions"; sessionId: string }
  | { page: "summary"; sessionId: string }
  | { page: "attempt"; sessionId: string; questionId: number };

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "s" && parts[1] && parts[2] === "q" && /^\d+$/.test(parts[3] ?? "")) {
    return { page: "attempt", sessionId: parts[1], questionId: Number(parts[3]) };
  }
  if (parts[0] === "s" && parts[1] && parts[2] === "summary") {
    return { page: "summary", sessionId: parts[1] };
  }
  if (parts[0] === "s" && parts[1]) {
    return parts[2] === "cv" ? { page: "cv", sessionId: parts[1] } : { page: "questions", sessionId: parts[1] };
  }
  if (parts[0] === "start") return { page: "setup" };
  if (parts[0] === "build") return parts[1] ? { page: "buildStep", buildId: parts[1] } : { page: "build" };
  return { page: "landing" };
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
