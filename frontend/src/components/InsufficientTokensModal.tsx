import { useState, useEffect } from 'react'
import { X, Zap } from 'lucide-react'
import { useTokens } from '../contexts/TokenContext'

interface TokensDetail { required: number; balance: number }

export function InsufficientTokensModal() {
  const [detail, setDetail] = useState<TokensDetail | null>(null)
  const { openRedeem } = useTokens()

  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<TokensDetail>
      setDetail(ce.detail)
    }
    window.addEventListener('insufficient-tokens', handler)
    return () => window.removeEventListener('insufficient-tokens', handler)
  }, [])

  if (!detail) return null

  const handleRedeem = () => {
    setDetail(null)
    openRedeem()
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-navy-light border border-slate-700 rounded-2xl w-full max-w-sm p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap size={18} className="text-yellow-400" />
            <h2 className="font-semibold text-slate-100">Недостаточно токенов</h2>
          </div>
          <button onClick={() => setDetail(null)} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="bg-navy rounded-xl p-4 mb-5 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Необходимо</span>
            <span className="text-yellow-300 font-semibold">{detail.required}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">На балансе</span>
            <span className="text-red-400 font-semibold">{detail.balance}</span>
          </div>
          <div className="border-t border-slate-700 pt-2 flex justify-between">
            <span className="text-slate-400">Не хватает</span>
            <span className="text-slate-300 font-semibold">{detail.required - detail.balance}</span>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setDetail(null)}
            className="flex-1 py-2.5 rounded-lg border border-slate-600 text-slate-300 text-sm
              hover:border-slate-500 hover:text-slate-100 transition-colors"
          >
            Закрыть
          </button>
          <button
            onClick={handleRedeem}
            className="flex-1 py-2.5 rounded-lg bg-accent hover:bg-accent-dark text-white text-sm
              font-medium transition-colors"
          >
            Активировать код
          </button>
        </div>
      </div>
    </div>
  )
}
