import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LogOut, PlusCircle, FileText, Coins, Shield } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useTokens } from '../contexts/TokenContext'

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const { balance, unlimited, isAdmin, refreshBalance, openRedeem } = useTokens()
  const navigate = useNavigate()

  // Refresh balance every time a protected page mounts
  useEffect(() => { refreshBalance() }, [refreshBalance])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-navy text-slate-100 flex flex-col">
      <header className="bg-navy-light border-b border-slate-700 px-6 py-3 flex items-center gap-6">
        <Link to="/" className="flex items-center gap-2 font-bold text-accent text-lg shrink-0">
          <img src="/logo-192.png" alt="" className="w-8 h-8 rounded-md object-cover" />
          ГОСТ Калькулятор
        </Link>

        <nav className="flex items-center gap-4 flex-1">
          <Link to="/new" className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-100 transition-colors">
            <PlusCircle size={15} />
            Новый проект
          </Link>
          <Link to="/format-gost" className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-100 transition-colors">
            <FileText size={15} />
            Форматировать
          </Link>
          {isAdmin && (
            <Link to="/admin" className="flex items-center gap-1.5 text-sm text-amber-400/80 hover:text-amber-300 transition-colors">
              <Shield size={15} />
              Админка
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-3 text-sm text-slate-400">
          {/* Token balance badge */}
          <button
            onClick={openRedeem}
            title="Нажмите чтобы активировать код"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium
              transition-colors hover:border-accent/70 hover:text-accent
              ${unlimited
                ? 'border-accent/50 text-accent bg-accent/10'
                : balance === null
                ? 'border-slate-700 text-slate-500'
                : balance === 0
                ? 'border-red-800 text-red-400 bg-red-950/30'
                : 'border-slate-600 text-slate-300'}`}
          >
            <Coins size={13} />
            {unlimited ? '∞' : balance === null ? '…' : balance}
          </button>

          <span className="hidden sm:block truncate max-w-[160px]">{user?.email}</span>
          <button onClick={handleLogout} className="flex items-center gap-1.5 hover:text-red-400 transition-colors">
            <LogOut size={15} />
            Выйти
          </button>
        </div>
      </header>

      <main className="flex-1 container mx-auto px-4 py-8 max-w-5xl">
        {children}
      </main>
    </div>
  )
}
