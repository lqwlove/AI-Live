import { Routes, Route } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { DashboardPage } from "@/pages/DashboardPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function App() {
  useWebSocket();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-auto bg-background">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/messages" element={<DashboardPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
