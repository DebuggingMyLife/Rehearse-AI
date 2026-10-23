import { StatusIndicators, StatusProblems, useHealth } from "./components/HealthBanner";
import ThemeToggle from "./components/ThemeToggle";
import { useHashRoute } from "./hooks/useHashRoute";
import AttemptPage from "./pages/AttemptPage";
import CvConfirmPage from "./pages/CvConfirmPage";
import QuestionsPage from "./pages/QuestionsPage";
import SetupPage from "./pages/SetupPage";
import SummaryPage from "./pages/SummaryPage";

export default function App() {
  const route = useHashRoute();
  const { health, backendDown, refresh } = useHealth();
  return (
    <div className="app">
      <header className="topbar">
        <a href="#/" className="brand">
          <h1>RehearseAI</h1>
        </a>
        <div className="topbar-right">
          <StatusIndicators health={health} backendDown={backendDown} />
          <ThemeToggle />
        </div>
      </header>
      <StatusProblems health={health} backendDown={backendDown} refresh={refresh} />
      <main>
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
