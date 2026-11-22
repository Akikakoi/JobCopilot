import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute, homePath, useAuth } from "./lib/auth";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SeekerJobsPage } from "./pages/SeekerJobsPage";
import { JobDetailPage } from "./pages/JobDetailPage";
import { ResumePage } from "./pages/ResumePage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { InterviewPage } from "./pages/InterviewPage";
import { SubscriptionsPage } from "./pages/SubscriptionsPage";
import { SavedJobsPage } from "./pages/SavedJobsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { CompanyPage } from "./pages/CompanyPage";
import { ChatPage } from "./pages/ChatPage";
import { EmployerJobsPage } from "./pages/EmployerJobsPage";
import { EmployerBoardPage } from "./pages/EmployerBoardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { MessagesPage } from "./pages/MessagesPage";

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
      </div>
    );
  }
  return <Navigate to={user ? homePath(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/seeker"
        element={
          <ProtectedRoute role="seeker">
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="jobs" replace />} />
        <Route path="jobs" element={<SeekerJobsPage />} />
        <Route path="jobs/:id" element={<JobDetailPage />} />
        <Route path="saved" element={<SavedJobsPage />} />
        <Route path="companies/:id" element={<CompanyPage />} />
        <Route path="resume" element={<ResumePage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="interview" element={<InterviewPage />} />
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="chat" element={<ChatPage />} />
      </Route>

      <Route
        path="/employer"
        element={
          <ProtectedRoute role="employer">
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="jobs" replace />} />
        <Route path="jobs" element={<EmployerJobsPage />} />
        <Route path="board" element={<EmployerBoardPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="chat" element={<ChatPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
