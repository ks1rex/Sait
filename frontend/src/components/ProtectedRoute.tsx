import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen bg-navy flex items-center justify-center text-slate-400">Загрузка...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}
