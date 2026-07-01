import { useState } from 'react'
import { X, KeyRound } from 'lucide-react'
import { useTokens } from '../contexts/TokenContext'
import { useToast } from './Toast'
import { apiPost, ApiError } from '../lib/api'

interface RedeemResponse { token_balance: number }

export function RedeemModal() {
  const { redeemOpen, closeRedeem, refreshBalance } = useTokens()
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  if (!redeemOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = code.trim()
    if (!trimmed) return
    setLoading(true)
    try {
      const res = await apiPost<RedeemResponse>('/redeem-code', { code: trimmed })
      await refreshBalance()
      toast(`Код активирован! Баланс: ${res.token_balance} ${plural(res.token_balance)}`, 'success')
      setCode('')
      closeRedeem()
    } catch (err: unknown) {
      const msg = err instanceof ApiError && err.status === 404
        ? 'Код не найден или уже использован'
        : err instanceof Error ? err.message : 'Ошибка активации'
      toast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={closeRedeem}>
      <div
        className="bg-navy-light border border-slate-700 rounded-2xl w-full max-w-sm p-6 shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <KeyRound size={18} className="text-accent" />
            <h2 className="font-semibold text-slate-100">Активировать код</h2>
          </div>
          <button onClick={closeRedeem} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        <p className="text-sm text-slate-400 mb-4">
          Введите код доступа для пополнения баланса токенов.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            value={code}
            onChange={e => setCode(e.target.value.toUpperCase())}
            placeholder="TEST-100"
            autoFocus
            className="bg-navy border border-slate-600 rounded-lg px-3 py-2.5 text-sm text-slate-100
              placeholder-slate-500 focus:outline-none focus:border-accent transition-colors
              font-mono tracking-widest text-center"
          />
          <button
            type="submit"
            disabled={loading || !code.trim()}
            className="py-2.5 rounded-lg bg-accent hover:bg-accent-dark text-white text-sm font-medium
              transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Проверка...' : 'Активировать'}
          </button>
        </form>
      </div>
    </div>
  )
}

function plural(n: number) {
  if (n === 1) return 'токен'
  if (n >= 2 && n <= 4) return 'токена'
  return 'токенов'
}
