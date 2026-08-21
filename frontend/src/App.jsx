import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './components/AuthProvider';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { JobExplorer } from './pages/JobExplorer';
import { JobDetail } from './pages/JobDetail';
import { QueueOverview } from './pages/QueueOverview';
import { RecurringJobs } from './pages/RecurringJobs';
import { WorkerStatus } from './pages/WorkerStatus';

const queryClient = new QueryClient();

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
};

const AppRoutes = () => {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<JobExplorer />} />
        <Route path="jobs/:id" element={<JobDetail />} />
        <Route path="queues" element={<QueueOverview />} />
        <Route path="recurring-jobs" element={<RecurringJobs />} />
        <Route path="workers" element={<WorkerStatus />} />
      </Route>
    </Routes>
  );
};

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
