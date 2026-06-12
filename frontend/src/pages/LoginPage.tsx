import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../components/Toast'

type Tab = 'login' | 'register'

export function LoginPage() {
  const [tab, setTab] = useState<Tab>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { login, register } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (tab === 'login') {
        await login(email, password)
        navigate('/')
      } else {
        await register(email, password)
        toast('Аккаунт создан. Войдите в систему.', 'success')
        setTab('login')
      }
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Ошибка', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-navy flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8 gap-2">
          <BookOpen size={40} className="text-accent" />
          <h1 className="text-2xl font-bold text-slate-100">ГОСТ Калькулятор</h1>
          <p className="text-sm text-slate-400">Расчёты и отчёты по ГОСТ</p>
        </div>

        <div className="bg-navy-light rounded-2xl border border-slate-700 p-6">
          <div className="flex rounded-lg bg-navy mb-6 p-1 gap-1">
            {(['login', 'register'] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors
                  ${tab === t ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200'}`}
              >
                {t === 'login' ? 'Войти' : 'Регистрация'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className="w-full bg-navy border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100
                  placeholder-slate-500 focus:outline-none focus:border-accent transition-colors"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Пароль</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full bg-navy border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100
                  placeholder-slate-500 focus:outline-none focus:border-accent transition-colors"
                placeholder="••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="mt-2 py-2.5 rounded-lg bg-accent hover:bg-accent-dark text-white font-medium text-sm
                transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Загрузка...' : tab === 'login' ? 'Войти' : 'Создать аккаунт'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
