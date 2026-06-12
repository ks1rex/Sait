import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { TokenProvider } from './contexts/TokenContext'
import { ToastProvider } from './components/Toast'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout'
import { RedeemModal } from './components/RedeemModal'
import { InsufficientTokensModal } from './components/InsufficientTokensModal'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { NewProjectPage } from './pages/NewProjectPage'
import { ReviewPage } from './pages/ReviewPage'
import { ResultPage } from './pages/ResultPage'
import { FormatGostPage } from './pages/FormatGostPage'
import { ChatPage } from './pages/ChatPage'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout><DashboardPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/new"
        element={
          <ProtectedRoute>
            <Layout><NewProjectPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/project/:id/review"
        element={
          <ProtectedRoute>
            <Layout><ReviewPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/project/:id/result"
        element={
          <ProtectedRoute>
            <Layout><ResultPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/project/:id/chat"
        element={
          <ProtectedRoute>
            <Layout><ChatPage /></Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/format-gost"
        element={
          <ProtectedRoute>
            <Layout><FormatGostPage /></Layout>
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <TokenProvider>
          <ToastProvider>
            <AppRoutes />
            {/* Global modals — rendered outside route tree so they survive navigation */}
            <RedeemModal />
            <InsufficientTokensModal />
          </ToastProvider>
        </TokenProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
