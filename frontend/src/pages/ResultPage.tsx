import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download, FileText, Loader2 } from 'lucide-react'
import { apiGet, apiPost } from '../lib/api'
import { useToast } from '../components/Toast'
import type { CalculationSpec } from '../types'

interface ProjectMeta {
  output_docx_url: string | null
  output_pdf_url: string | null
  status: string
}

interface GenerateResult {
  docx_url: string
  pdf_url: string | null
  warning: string | null
}

export function ResultPage() {
  const { id } = useParams<{ id: string }>()
  const toast = useToast()

  const [spec, setSpec] = useState<CalculationSpec | null>(null)
  const [meta, setMeta] = useState<ProjectMeta | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    Promise.all([
      apiGet<CalculationSpec>(`/spec/${id}`),
      apiGet<ProjectMeta>(`/project/${id}`),
    ])
      .then(([s, m]) => { setSpec(s); setMeta(m) })
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false))
  }, [id, toast])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const result = await apiPost<GenerateResult>(`/generate?project_id=${id}`)
      setMeta(prev => ({
        ...prev!,
        output_docx_url: result.docx_url,
        output_pdf_url: result.pdf_url ?? null,
      }))
      if (result.warning) toast(result.warning, 'info')
      else toast('Документ сформирован', 'success')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Ошибка генерации', 'error')
    } finally {
      setGenerating(false)
    }
  }

  if (loading) return <div className="flex justify-center py-20 text-slate-400">Загрузка результатов...</div>
  if (!spec) return <div className="text-center py-20 text-slate-500">Результаты не найдены</div>

  const allSteps = spec.sections.flatMap(s => s.steps)
  const computed = allSteps.filter(st => st.value !== null && st.value !== undefined)

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">{spec.title || 'Результаты расчёта'}</h1>
          <p className="text-sm text-slate-400 mt-1">
            Вычислено {computed.length} из {allSteps.length} шагов
          </p>
        </div>

        <div className="flex gap-2 shrink-0">
          {meta?.output_docx_url && (
            <a
              href={meta.output_docx_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-600 text-sm text-slate-300
                hover:border-accent/60 hover:text-slate-100 transition-colors"
            >
              <Download size={14} />
              DOCX
            </a>
          )}
          {meta?.output_pdf_url && (
            <a
              href={meta.output_pdf_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-600 text-sm text-slate-300
                hover:border-accent/60 hover:text-slate-100 transition-colors"
            >
              <Download size={14} />
              PDF
            </a>
          )}
          {!meta?.output_docx_url && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent hover:bg-accent-dark text-white text-sm
                font-medium transition-colors disabled:opacity-50"
            >
              {generating ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
              {generating ? 'Генерация...' : 'Сформировать отчёт'}
            </button>
          )}
        </div>
      </div>

      {/* Results table */}
      {spec.sections.map(sec => (
        <div key={sec.id} className="bg-navy-light border border-slate-700 rounded-xl mb-4 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-700">
            <h2 className="font-semibold text-slate-200">{sec.title}</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-500 border-b border-slate-700">
                  <th className="text-left px-4 py-2 font-normal w-28">Обозначение</th>
                  <th className="text-left px-4 py-2 font-normal">Описание</th>
                  <th className="text-left px-4 py-2 font-normal">Формула</th>
                  <th className="text-right px-4 py-2 font-normal w-28">Результат</th>
                  <th className="text-left px-4 py-2 font-normal w-20">Ед. изм.</th>
                </tr>
              </thead>
              <tbody>
                {sec.steps.map(step => (
                  <tr key={step.id} className="border-b border-slate-700/50">
                    <td className="px-4 py-2.5 font-mono text-xs text-accent">{step.result_symbol}</td>
                    <td className="px-4 py-2.5 text-slate-300 text-xs">{step.description}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-400">{step.formula}</td>
                    <td className="px-4 py-2.5 text-right">
                      {step.value !== null && step.value !== undefined ? (
                        <span className="text-slate-100 font-medium">
                          {typeof step.value === 'number'
                            ? step.value.toFixed(step.rounding ?? 2)
                            : step.value}
                        </span>
                      ) : (
                        <span className="text-red-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 text-xs">{step.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}
