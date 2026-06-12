import { Link, useNavigate } from 'react-router-dom'
import { LogOut, BookOpen, PlusCircle, FileText } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-navy text-slate-100 flex flex-col">
      <header className="bg-navy-light border-b border-slate-700 px-6 py-3 flex items-center gap-6">
        <Link to="/" className="flex items-center gap-2 font-bold text-accent text-lg shrink-0">
          <BookOpen size={20} />
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
        </nav>

        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span className="hidden sm:block truncate max-w-[180px]">{user?.email}</span>
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
