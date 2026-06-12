import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PlusCircle, ChevronRight } from 'lucide-react'
import { supabase } from '../lib/supabase'
import { StatusBadge } from '../components/StatusBadge'
import { useToast } from '../components/Toast'
import type { Project } from '../types'

export function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  useEffect(() => {
    supabase
      .from('projects')
      .select('id, title, status, generation_mode, created_at, output_docx_path, output_pdf_path')
      .order('created_at', { ascending: false })
      .then(({ data, error }) => {
        if (error) toast(error.message, 'error')
        else setProjects((data as Project[]) ?? [])
        setLoading(false)
      })
  }, [toast])

  const projectUrl = (p: Project) => {
    if (p.status === 'done') return `/project/${p.id}/result`
    if (p.status === 'extracted' || p.status === 'computed') return `/project/${p.id}/review`
    return null
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-400">
        Загрузка проектов...
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-100">Мои проекты</h1>
        <Link
          to="/new"
          className="flex items-center gap-2 bg-accent hover:bg-accent-dark text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <PlusCircle size={16} />
          Новый проект
        </Link>
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <p className="text-lg mb-2">Проектов пока нет</p>
          <Link to="/new" className="text-accent hover:underline text-sm">Создать первый проект</Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {projects.map(p => {
            const url = projectUrl(p)
            const date = new Date(p.created_at).toLocaleDateString('ru-RU', {
              day: '2-digit', month: '2-digit', year: 'numeric'
            })
            const card = (
              <div className={`bg-navy-light border border-slate-700 rounded-xl px-5 py-4 flex items-center gap-4
                ${url ? 'hover:border-accent/50 transition-colors cursor-pointer' : ''}`}>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-100 truncate">{p.title || 'Без названия'}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{date}</p>
                </div>
                <StatusBadge status={p.status} />
                {url && <ChevronRight size={16} className="text-slate-500 shrink-0" />}
              </div>
            )
            return url ? <Link key={p.id} to={url}>{card}</Link> : <div key={p.id}>{card}</div>
          })}
        </div>
      )}
    </div>
  )
}
