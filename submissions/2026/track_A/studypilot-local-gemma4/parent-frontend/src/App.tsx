import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppHeader } from "./components/AppHeader";
import { BriefView } from "./views/BriefView";
import { CalibrationView } from "./views/CalibrationView";
import { ResultView } from "./views/ResultView";
import { canonicalParentPath } from "./workspace";

function ParentRouteFallback() {
  const location = useLocation();
  return <Navigate to={canonicalParentPath(location.pathname)} replace />;
}

export function App() {
  return (
    <div className="app">
      <AppHeader />
      <Routes>
        <Route path="/brief" element={<BriefView />} />
        <Route path="/calibration" element={<CalibrationView />} />
        <Route path="/result" element={<ResultView />} />
        <Route path="*" element={<ParentRouteFallback />} />
      </Routes>
    </div>
  );
}
