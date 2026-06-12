import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { apiGet } from '../lib/api'

interface MeResponse { token_balance: number; unlimited_access: boolean; is_admin: boolean }

interface TokenCtx {
  balance: number | null
  unlimited: boolean
  isAdmin: boolean
  refreshBalance: () => Promise<void>
  openRedeem: () => void
  closeRedeem: () => void
  redeemOpen: boolean
}

const Ctx = createContext<TokenCtx | null>(null)

export function TokenProvider({ children }: { children: ReactNode }) {
  const [balance, setBalance] = useState<number | null>(null)
  const [unlimited, setUnlimited] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [redeemOpen, setRedeemOpen] = useState(false)

  const refreshBalance = useCallback(async () => {
    try {
      const data = await apiGet<MeResponse>('/me')
      setBalance(data.token_balance)
      setUnlimited(data.unlimited_access)
      setIsAdmin(data.is_admin ?? false)
    } catch {
      // not authenticated yet or network error — silently ignore
    }
  }, [])

  return (
    <Ctx.Provider value={{
      balance,
      unlimited,
      isAdmin,
      refreshBalance,
      openRedeem: () => setRedeemOpen(true),
      closeRedeem: () => setRedeemOpen(false),
      redeemOpen,
    }}>
      {children}
    </Ctx.Provider>
  )
}

export function useTokens() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTokens must be inside TokenProvider')
  return ctx
}
