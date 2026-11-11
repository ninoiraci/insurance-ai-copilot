import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppConfigProvider } from './components/AppConfigContext';
import { Layout } from './components/Layout';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { ConversationDetailPage } from './pages/ConversationDetailPage';
import { CustomerDetailPage } from './pages/CustomerDetailPage';
import { CustomersPage } from './pages/CustomersPage';
import { DashboardPage } from './pages/DashboardPage';
import { EvaluationsPage } from './pages/EvaluationsPage';
import { InboxPage } from './pages/InboxPage';
import { KnowledgeBasePage } from './pages/KnowledgeBasePage';

export function App() {
  return (
    <AppConfigProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="inbox" element={<InboxPage />} />
            <Route path="inbox/:conversationId" element={<ConversationDetailPage />} />
            <Route path="customers" element={<CustomersPage />} />
            <Route path="customers/:customerId" element={<CustomerDetailPage />} />
            <Route path="knowledge" element={<KnowledgeBasePage />} />
            <Route path="evaluations" element={<EvaluationsPage />} />
            <Route path="audit" element={<AuditLogsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppConfigProvider>
  );
}
