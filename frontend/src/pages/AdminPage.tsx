import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users, Key, BarChart3, Shield, Coins, CheckCircle, XCircle,
  Copy, Check, TrendingDown, Loader2, RefreshCw,
} from 'lucide-react'
import { apiGet, apiPost, ApiError } from '../lib/api'
import { useToast } from '../components/Toast'
import { useTokens } from '../contexts/TokenContext'

// ── Types ─────────────────────────────────────────────────────────────────────

interface AdminUser {
  id: string
  email: string
  token_balance: number
  unlimited_access: boolean
  is_admin: boolean
  created_at: string
}

interface AdminCode {
  id: string
  code: string
  tokens: number
  used_by: string | null
  used_by_email: string
  used_at: string | null
  created_at: string
}

interface AdminStats {
  total_users: number
  total_token_balance: number
  total_tokens_spent: number
  projects_by_status: Record<string, number>
  projects_by_mode: Record<string, number>
  ai_usage_all: { input_tokens: number; output_tokens: number }
  ai_usage_7d: { input_tokens: number; output_tokens: number }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(s: string | null | undefined) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function fmtNum(n: number) {
  return n.toLocaleString('ru-RU')
}

const STATUS_LABELS: Record<string, string> = {
  uploaded: 'Загружен', extracted: 'Распознан', computed: 'Вычислен',
  done: 'Готов', error: 'Ошибка',
}
const MODE_LABELS: Record<string, string> = {
  universal: 'Универсальный', fixed_template: 'По шаблону',
  custom_template: 'Свой шаблон', unknown: 'Неизвестно',
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TabBtn({ active, onClick, icon, label }: {
  active: boolean; onClick: () => void; icon: React.ReactNode; label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
        ${active ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-navy-light'}`}
    >
      {icon}
      {label}
    </button>
  )
}

function StatCard({ title, value, icon, sub }: {
  title: string; value: number | string; icon: React.ReactNode; sub?: string
}) {
  return (
    <div className="bg-navy-light border border-slate-700 rounded-xl p-4">
      <div className="flex items-center gap-2 text-slate-400 text-xs mb-2">
        {icon}
        {title}
      </div>
      <p className="text-2xl font-bold text-slate-100">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}

function Toggle({ label, value, onChange, disabled }: {
  label: string; value: boolean; onChange: (v: boolean) => void; disabled?: boolean
}) {
  return (
    <button
      onClick={() => onChange(!value)}
      disabled={disabled}
      className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors
        disabled:opacity-50 disabled:cursor-not-allowed
        ${value
          ? 'border-accent/70 bg-accent/15 text-accent'
          : 'border-slate-700 bg-navy text-slate-500 hover:border-slate-500'}`}
    >
      {value ? <CheckCircle size={12} /> : <XCircle size={12} />}
      {label}
    </button>
  )
}

function Spinner() {
  return (
    <div className="flex justify-center py-12">
      <Loader2 size={28} className="animate-spin text-slate-500" />
    </div>
  )
}

// ── UserCard ──────────────────────────────────────────────────────────────────

function UserCard({ user, onUpdate }: { user: AdminUser; onUpdate: (u: AdminUser) => void }) {
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [adjusting, setAdjusting] = useState(false)
  const [flagging, setFlagging] = useState(false)
  const toast = useToast()

  const handleAdjust = async () => {
    const n = parseInt(amount)
    if (isNaN(n) || n === 0 || !reason.trim()) return
    setAdjusting(true)
    try {
      const r = await apiPost<{ new_balance: number }>(`/admin/users/${user.id}/adjust-tokens`, {
        amount: n, reason: reason.trim(),
      })
      onUpdate({ ...user, token_balance: r.new_balance })
      toast(`Баланс: ${r.new_balance} токенов`, 'success')
      setAmount('')
      setReason('')
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Ошибка', 'error')
    } finally {
      setAdjusting(false)
    }
  }

  const toggleFlag = async (flag: 'unlimited_access' | 'is_admin', value: boolean) => {
    setFlagging(true)
    try {
      await apiPost(`/admin/users/${user.id}/set-flag`, { flag, value })
      onUpdate({ ...user, [flag]: value })
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Ошибка', 'error')
    } finally {
      setFlagging(false)
    }
  }

  const amountN = parseInt(amount)
  const canAdjust = !isNaN(amountN) && amountN !== 0 && reason.trim().length > 0

  return (
    <div className="bg-navy-light border border-slate-700 rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-100 truncate">{user.email || '—'}</p>
          <p className="text-xs text-slate-500">{fmtDate(user.created_at)}</p>
        </div>
        <span className="shrink-0 text-sm font-bold text-accent tabular-nums">
          {user.token_balance} т
        </span>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Toggle label="Безлимит" value={user.unlimited_access}
          onChange={v => toggleFlag('unlimited_access', v)} disabled={flagging} />
        <Toggle label="Админ" value={user.is_admin}
          onChange={v => toggleFlag('is_admin', v)} disabled={flagging} />
      </div>

      <div className="flex gap-2">
        <input
          type="number"
          value={amount}
          onChange={e => setAmount(e.target.value)}
          placeholder="±токенов"
          className="w-24 shrink-0 bg-navy border border-slate-600 rounded-lg px-2 py-1.5 text-xs text-slate-100
            placeholder-slate-500 focus:outline-none focus:border-accent"
        />
        <input
          type="text"
          value={reason}
          onChange={e => setReason(e.target.value)}
          placeholder="Причина"
          className="flex-1 min-w-0 bg-navy border border-slate-600 rounded-lg px-2 py-1.5 text-xs text-slate-100
            placeholder-slate-500 focus:outline-none focus:border-accent"
        />
        <button
          onClick={handleAdjust}
          disabled={adjusting || !canAdjust}
          className="shrink-0 px-3 py-1.5 rounded-lg bg-accent hover:bg-accent-dark text-white text-xs
            font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {adjusting ? <Loader2 size={12} className="animate-spin" /> : 'Применить'}
        </button>
      </div>
    </div>
  )
}

// ── Users Tab ─────────────────────────────────────────────────────────────────

function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  const load = useCallback(() => {
    setLoading(true)
    apiGet<AdminUser[]>('/admin/users')
      .then(setUsers)
      .catch(e => toast(e instanceof Error ? e.message : 'Ошибка загрузки', 'error'))
      .finally(() => setLoading(false))
  }, [toast])

  useEffect(() => { load() }, [load])

  const updateUser = (updated: AdminUser) =>
    setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-400">{users.length} пользователей</p>
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors">
          <RefreshCw size={13} />
          Обновить
        </button>
      </div>
      {loading ? <Spinner /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {users.map(u => <UserCard key={u.id} user={u} onUpdate={updateUser} />)}
          {users.length === 0 && (
            <p className="text-sm text-slate-500 col-span-2 text-center py-8">Нет пользователей</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Codes Tab ─────────────────────────────────────────────────────────────────

function CodesTab() {
  const [codes, setCodes] = useState<AdminCode[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'used' | 'free'>('all')
  const [genCount, setGenCount] = useState(1)
  const [genTokens, setGenTokens] = useState(100)
  const [genPrefix, setGenPrefix] = useState('CODE')
  const [generating, setGenerating] = useState(false)
  const [newCodes, setNewCodes] = useState<string[]>([])
  const [copied, setCopied] = useState(false)
  const toast = useToast()

  const loadCodes = useCallback((f: 'all' | 'used' | 'free') => {
    setLoading(true)
    const qs = f === 'all' ? '' : `?used=${f === 'used'}`
    apiGet<AdminCode[]>(`/admin/codes${qs}`)
      .then(setCodes)
      .catch(e => toast(e instanceof Error ? e.message : 'Ошибка', 'error'))
      .finally(() => setLoading(false))
  }, [toast])

  useEffect(() => { loadCodes(filter) }, [filter, loadCodes])

  const handleGenerate = async () => {
    if (genCount < 1 || genCount > 100 || genTokens < 1 || !genPrefix.trim()) return
    setGenerating(true)
    try {
      const r = await apiPost<{ codes: string[] }>('/admin/codes/generate', {
        count: genCount, tokens: genTokens, prefix: genPrefix.trim().toUpperCase(),
      })
      setNewCodes(r.codes)
      toast(`Сгенерировано ${r.codes.length} кодов`, 'success')
      loadCodes(filter)
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Ошибка генерации', 'error')
    } finally {
      setGenerating(false)
    }
  }

  const copyAll = () => {
    navigator.clipboard.writeText(newCodes.join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Generate form */}
      <div className="bg-navy-light border border-slate-700 rounded-xl p-4">
        <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Генерация кодов</p>
        <div className="flex flex-wrap gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500">Количество</label>
            <input type="number" value={genCount} min={1} max={100}
              onChange={e => setGenCount(Math.max(1, Math.min(100, parseInt(e.target.value) || 1)))}
              className="w-24 bg-navy border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100
                focus:outline-none focus:border-accent" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500">Токенов на код</label>
            <input type="number" value={genTokens} min={1}
              onChange={e => setGenTokens(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-28 bg-navy border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100
                focus:outline-none focus:border-accent" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500">Префикс</label>
            <input type="text" value={genPrefix} maxLength={12}
              onChange={e => setGenPrefix(e.target.value.toUpperCase())}
              className="w-28 bg-navy border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100
                focus:outline-none focus:border-accent" />
          </div>
          <div className="flex flex-col justify-end">
            <button onClick={handleGenerate} disabled={generating}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent hover:bg-accent-dark
                text-white text-sm font-medium transition-colors disabled:opacity-50">
              {generating ? <Loader2 size={14} className="animate-spin" /> : <Key size={14} />}
              Сгенерировать
            </button>
          </div>
        </div>
      </div>

      {/* Generated codes result */}
      {newCodes.length > 0 && (
        <div className="bg-navy-light border border-accent/40 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-slate-200">
              Новые коды ({newCodes.length}) — по {genTokens} токенов
            </p>
            <button onClick={copyAll}
              className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-dark transition-colors">
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? 'Скопировано' : 'Скопировать всё'}
            </button>
          </div>
          <div className="font-mono text-xs text-slate-300 space-y-1 max-h-48 overflow-y-auto">
            {newCodes.map(c => <div key={c} className="py-0.5">{c}</div>)}
          </div>
        </div>
      )}

      {/* Filter + code list */}
      <div>
        <div className="flex gap-2 mb-4">
          {(['all', 'free', 'used'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors
                ${filter === f ? 'border-accent bg-accent/15 text-accent' : 'border-slate-700 text-slate-500 hover:border-slate-500'}`}>
              {f === 'all' ? 'Все' : f === 'free' ? 'Свободные' : 'Использованные'}
            </button>
          ))}
        </div>

        {loading ? <Spinner /> : (
          <div className="overflow-x-auto rounded-xl border border-slate-700">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-700 bg-navy-light">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Код</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Токены</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Использован</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Когда</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Создан</th>
                </tr>
              </thead>
              <tbody>
                {codes.map(c => (
                  <tr key={c.id} className="border-b border-slate-800 hover:bg-navy-light/50 transition-colors">
                    <td className="px-4 py-3 font-mono text-slate-200">{c.code}</td>
                    <td className="px-4 py-3 text-accent font-medium">{c.tokens}</td>
                    <td className="px-4 py-3">
                      {c.used_by_email
                        ? <span className="text-slate-300">{c.used_by_email}</span>
                        : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{fmtDate(c.used_at)}</td>
                    <td className="px-4 py-3 text-slate-500">{fmtDate(c.created_at)}</td>
                  </tr>
                ))}
                {codes.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-slate-600">Нет кодов</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Stats Tab ─────────────────────────────────────────────────────────────────

function StatsTab() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  useEffect(() => {
    apiGet<AdminStats>('/admin/stats')
      .then(setStats)
      .catch(e => toast(e instanceof Error ? e.message : 'Ошибка загрузки', 'error'))
      .finally(() => setLoading(false))
  }, [toast])

  if (loading) return <Spinner />
  if (!stats) return <p className="text-slate-500 text-sm">Не удалось загрузить статистику</p>

  const totalProjects = Object.values(stats.projects_by_status).reduce((a, b) => a + b, 0)

  return (
    <div className="space-y-6">
      {/* Top metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard title="Пользователей" value={fmtNum(stats.total_users)} icon={<Users size={13} />} />
        <StatCard title="Токенов в системе" value={fmtNum(stats.total_token_balance)} icon={<Coins size={13} />}
          sub="суммарный баланс" />
        <StatCard title="Токенов потрачено" value={fmtNum(stats.total_tokens_spent)} icon={<TrendingDown size={13} />}
          sub="за всё время" />
      </div>

      {/* Projects */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-navy-light border border-slate-700 rounded-xl p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">
            Проекты по статусу ({totalProjects})
          </p>
          <div className="space-y-1.5">
            {Object.entries(stats.projects_by_status).map(([s, n]) => (
              <div key={s} className="flex justify-between text-sm">
                <span className="text-slate-400">{STATUS_LABELS[s] ?? s}</span>
                <span className="text-slate-200 font-medium tabular-nums">{n}</span>
              </div>
            ))}
            {Object.keys(stats.projects_by_status).length === 0 &&
              <p className="text-slate-600 text-sm">Нет проектов</p>}
          </div>
        </div>

        <div className="bg-navy-light border border-slate-700 rounded-xl p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Проекты по режиму</p>
          <div className="space-y-1.5">
            {Object.entries(stats.projects_by_mode).map(([m, n]) => (
              <div key={m} className="flex justify-between text-sm">
                <span className="text-slate-400">{MODE_LABELS[m] ?? m}</span>
                <span className="text-slate-200 font-medium tabular-nums">{n}</span>
              </div>
            ))}
            {Object.keys(stats.projects_by_mode).length === 0 &&
              <p className="text-slate-600 text-sm">Нет проектов</p>}
          </div>
        </div>
      </div>

      {/* AI usage */}
      <div className="bg-navy-light border border-slate-700 rounded-xl p-4">
        <p className="text-xs text-slate-500 uppercase tracking-wider mb-4">AI-токены (не путать с токенами доступа)</p>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="text-xs text-slate-500 mb-2">За всё время</p>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Входящих</span>
                <span className="text-slate-200 tabular-nums">{fmtNum(stats.ai_usage_all.input_tokens)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Исходящих</span>
                <span className="text-slate-200 tabular-nums">{fmtNum(stats.ai_usage_all.output_tokens)}</span>
              </div>
            </div>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-2">За 7 дней</p>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Входящих</span>
                <span className="text-slate-200 tabular-nums">{fmtNum(stats.ai_usage_7d.input_tokens)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Исходящих</span>
                <span className="text-slate-200 tabular-nums">{fmtNum(stats.ai_usage_7d.output_tokens)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = 'users' | 'codes' | 'stats'

export function AdminPage() {
  const { isAdmin, balance } = useTokens()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('users')

  useEffect(() => {
    if (balance !== null && !isAdmin) navigate('/', { replace: true })
  }, [balance, isAdmin, navigate])

  // Wait for balance to load before checking access
  if (balance === null) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500 gap-2">
        <Loader2 size={18} className="animate-spin" />
        Проверка прав доступа...
      </div>
    )
  }

  if (!isAdmin) return null

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Shield size={22} className="text-amber-400" />
        <h1 className="text-2xl font-bold text-slate-100">Панель администратора</h1>
      </div>

      <div className="flex gap-2 mb-6 border-b border-slate-800 pb-3">
        <TabBtn active={tab === 'users'} onClick={() => setTab('users')}
          icon={<Users size={15} />} label="Пользователи" />
        <TabBtn active={tab === 'codes'} onClick={() => setTab('codes')}
          icon={<Key size={15} />} label="Коды доступа" />
        <TabBtn active={tab === 'stats'} onClick={() => setTab('stats')}
          icon={<BarChart3 size={15} />} label="Статистика" />
      </div>

      {tab === 'users' && <UsersTab />}
      {tab === 'codes' && <CodesTab />}
      {tab === 'stats' && <StatsTab />}
    </div>
  )
}
