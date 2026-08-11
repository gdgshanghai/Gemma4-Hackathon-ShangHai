import { useEffect, useState } from "react";
import { LoaderCircle, RotateCw } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { AppHeader } from "./components/AppHeader";
import { getDemoScenario, resetDemoEvening } from "./api/client";
import { canonicalPathForStage } from "./routing";
import { useSession } from "./state/session";
import { IntakeView } from "./views/IntakeView";
import { OverviewView } from "./views/OverviewView";
import { ReviewView } from "./views/ReviewView";
import { RouteView } from "./views/RouteView";

export function App() {
  const {
    session,
    isRestoring,
    restoreError,
    notice,
    clearNotice,
    acceptResponse,
    handleActionError,
    retryRestore,
  } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [reviewOpen, setReviewOpen] = useState(false);
  const demoMode = import.meta.env.VITE_DEMO_MODE === "true";
  const demoQuery = useQuery({
    queryKey: ["demo", "scenario"],
    queryFn: getDemoScenario,
    enabled: demoMode,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const demoOutdated = Boolean(
    session && demoQuery.data && session.planning_date !== demoQuery.data.planning_date,
  );

  useEffect(() => {
    if (isRestoring || restoreError) return;
    if (!session) {
      if (location.pathname !== "/intake") navigate("/intake", { replace: true });
      return;
    }
    if (session.stage !== "committed" && reviewOpen) setReviewOpen(false);
    if (session.stage === "committed" && reviewOpen && location.pathname === "/review") return;
    const canonicalPath = canonicalPathForStage(session.stage);
    if (location.pathname !== canonicalPath) navigate(canonicalPath, { replace: true });
  }, [isRestoring, location.pathname, navigate, restoreError, reviewOpen, session]);

  function openReview() {
    setReviewOpen(true);
    navigate("/review");
  }

  async function resetDemo() {
    try {
      const response = await resetDemoEvening(session?.session_id ?? null);
      acceptResponse(response);
      setReviewOpen(false);
      navigate("/intake", { replace: true });
    } catch (error) {
      await handleActionError(error);
    }
  }

  return (
    <div className="app">
      <AppHeader
        session={session}
        reviewOpen={reviewOpen}
        notice={notice}
        demoMode={demoMode}
        demoOutdated={demoOutdated}
        onResetDemo={resetDemo}
        onDismissNotice={clearNotice}
      />
      {isRestoring ? (
        <main className="center-state" aria-live="polite">
          <LoaderCircle className="spin" size={28} />
          <strong>正在恢复今晚的计划...</strong>
        </main>
      ) : restoreError ? (
        <main className="center-state">
          <strong>暂时无法读取今晚的计划</strong>
          <button className="button secondary" type="button" onClick={() => void retryRestore()}>
            <RotateCw size={18} />重新连接
          </button>
        </main>
      ) : (
        <Routes>
          <Route path="/intake" element={<IntakeView />} />
          <Route path="/overview" element={<OverviewView />} />
          <Route path="/route" element={<RouteView onOpenReview={openReview} />} />
          <Route path="/review" element={<ReviewView />} />
          <Route path="*" element={<Navigate to={session ? canonicalPathForStage(session.stage) : "/intake"} replace />} />
        </Routes>
      )}
    </div>
  );
}
