import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { DebugBranchPage } from "./pages/DebugBranchPage";
import DebugBranchLivePage from "./pages/DebugBranchLivePage";
import { DebugJobsPage } from "./pages/DebugJobsPage";
import { DebugParserPage } from "./pages/DebugPage";
import DebugLivePage from "./pages/DebugLivePage";
import { MainPage } from "./pages/MainPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route
          path="/debug"
          element={<Navigate to="/debug/parser" replace />}
        />
        <Route path="/debug/parser" element={<DebugParserPage />} />
        <Route path="/debug/jobs" element={<DebugJobsPage />} />
        <Route path="/debug/live" element={<DebugLivePage />} />
        <Route path="/debug/branches" element={<DebugBranchPage />} />
        <Route path="/debug/branch-live" element={<DebugBranchLivePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
