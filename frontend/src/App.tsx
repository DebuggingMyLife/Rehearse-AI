import { StatusIndicators, StatusProblems, useHealth } from "./components/HealthBanner";
import Logo from "./components/Logo";
import ThemeToggle from "./components/ThemeToggle";
import { useEffect } from "react";
import { useHashRoute, type Route } from "./hooks/useHashRoute";
import AttemptPage from "./pages/AttemptPage";
import CvConfirmPage from "./pages/CvConfirmPage";
import LandingPage from "./pages/LandingPage";
import QuestionsPage from "./pages/QuestionsPage";
import SetupPage from "./pages/SetupPage";
import SummaryPage from "./pages/SummaryPage";

function routeKey(route: Route): string {
  return [route.page, "sessionId" in route ? route.sessionId : "", "questionId" in route ? route.questionId : ""].join(":");
}

export default function App() {
  const route = useHashRoute();
  const { health, backendDown, refresh } = useHealth();
  const pageKey = routeKey(route);

  // New page: start at the top rather than wherever the last one was scrolled to.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pageKey]);
  return (
    <div className="app">
      <header className="topbar">
        <a href="#/" className="brand" aria-label="RehearseAI home">
          <h1>
            <Logo />
          </h1>
        </a>
        <div className="topbar-right">
          <StatusIndicators health={health} backendDown={backendDown} />
          <ThemeToggle />
        </div>
      </header>
      <StatusProblems health={health} backendDown={backendDown} refresh={refresh} />
      {/* Keyed by route so each page mounts fresh and plays the enter animation. */}
      <main key={pageKey} className="page-enter">
        {route.page === "landing" && <LandingPage />}
        {route.page === "setup" && <SetupPage />}
        {route.page === "cv" && <CvConfirmPage key={route.sessionId} sessionId={route.sessionId} />}
        {route.page === "attempt" && (
          <AttemptPage key={route.questionId} sessionId={route.sessionId} questionId={route.questionId} />
        )}
        {route.page === "summary" && <SummaryPage key={route.sessionId} sessionId={route.sessionId} />}
        {route.page === "questions" && <QuestionsPage key={route.sessionId} sessionId={route.sessionId} />}
      </main>
    </div>
  );
}
