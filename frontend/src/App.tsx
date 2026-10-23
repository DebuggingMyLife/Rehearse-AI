import HealthBanner from "./components/HealthBanner";
import { useHashRoute } from "./hooks/useHashRoute";
import AttemptPage from "./pages/AttemptPage";
import CvConfirmPage from "./pages/CvConfirmPage";
import QuestionsPage from "./pages/QuestionsPage";
import SetupPage from "./pages/SetupPage";
import SummaryPage from "./pages/SummaryPage";

export default function App() {
  const route = useHashRoute();
  return (
    <div className="app">
      <header>
        <a href="#/" className="brand">
          <h1>Retake</h1>
        </a>
        <p className="tagline">Local AI mock interviews</p>
      </header>
      <HealthBanner />
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
