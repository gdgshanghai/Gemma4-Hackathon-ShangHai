import { Navigate, Route, Routes } from "react-router-dom"
import AdminHome from "@/routes/admin/AdminHome"
import ViewHome from "@/routes/view/ViewHome"

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/admin" replace />} />
      <Route path="/admin" element={<AdminHome />} />
      <Route path="/view" element={<ViewHome />} />
      <Route path="*" element={<div className="p-10 text-muted-foreground">404 · 路由不存在</div>} />
    </Routes>
  )
}
