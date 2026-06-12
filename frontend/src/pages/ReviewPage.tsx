import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Save, Play, ChevronDown, ChevronRight } from 'lucide-react'
import { apiGet, apiPut, apiPost } from '../lib/api'
import { useToast } from '../components/Toast'
import type { CalculationSpec, InputDataItem, CalculationStep } from '../types'

export function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [spec, setSpec] = useState<CalculationSpec | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [computing, setComputing] = useState(false)
  const [openSections, setOpenSections] = useState<Set<string>>(new Set())

  useEffect(() => {
    apiGet<CalculationSpec>(`/spec/${id}`)
      .then(data => {
        setSpec(data)
        setOpenSections(new Set(data.sections?.map(s => s.id) ?? []))
      })
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false))
  }, [id, toast])

  const updateInput = (idx: number, field: keyof InputDataItem, value: string | number) => {
    setSpec(prev => {
      if (!prev) return prev
      const input_data = [...prev.input_data]
      input_data[idx] = { ...input_data[idx], [field]: field === 'value' ? Number(value) || value : value }
      return { ...prev, input_data }
    })
  }

  const updateStep = (secIdx: number, stepIdx: number, field: keyof CalculationStep, value: string) => {
    setSpec(prev => {
      if (!prev) return prev
      const sections = prev.sections.map((sec, si) => {
        if (si !== secIdx) return sec
        const steps = sec.steps.map((st, ti) =>
          ti !== stepIdx ? st : { ...st, [field]: value }
        )
        return { ...sec, steps }
      })
      return { ...prev, sections }
    })
  }

  const handleSave = async () => {
    if (!spec) return
    setSaving(true)
    try {
      await apiPut(`/spec/${id}`, spec)
      toast('Спецификация сохранена', 'success')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Ошибка сохранения', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleCompute = async () => {
    if (!spec) return
    setSaving(true)
    try {
      await apiPut(`/spec/${id}`, spec)
    } catch { /* save error already visible via handleSave */ }
    setSaving(false)
    setComputing(true)
    try {
      await apiPost(`/compute?project_id=${id}`)
      navigate(`/project/${id}/result`)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Ошибка расчёта', 'error')
    } finally {
      setComputing(false)
    }
  }

  const toggleSection = (id: string) => {
    setOpenSections(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  if (loading) return <div className="flex justify-center py-20 text-slate-400">Загрузка спецификации...</div>
  if (!spec) return <div className="text-center py-20 text-slate-500">Спецификация не найдена</div>
  // Defensive: a custom_template project has no editable spec — don't crash here.
  if (!Array.isArray(spec.input_data) || !Array.isArray(spec.sections)) {
    return (
      <div className="text-center py-20 text-slate-500">
        Для этого проекта нет редактируемой спецификации.{' '}
        <button onClick={() => navigate(`/project/${id}/result`)} className="text-accent hover:underline">
          Открыть результат
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">{spec.title || 'Проверка спецификации'}</h1>
          <p className="text-sm text-slate-400 mt-1">Проверьте и при необходимости скорректируйте данные</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-600 text-sm text-slate-300
              hover:border-accent/60 hover:text-slate-100 transition-colors disabled:opacity-50"
          >
            <Save size={14} />
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
          <button
            onClick={handleCompute}
            disabled={computing || saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent hover:bg-accent-dark text-white text-sm
              font-medium transition-colors disabled:opacity-50"
          >
            <Play size={14} />
            {computing ? 'Расчёт...' : 'Рассчитать'}
          </button>
        </div>
      </div>

      {/* Input data */}
      <section className="bg-navy-light border border-slate-700 rounded-xl mb-6 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-700">
          <h2 className="font-semibold text-slate-200">Исходные данные</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 border-b border-slate-700">
                <th className="text-left px-4 py-2.5 font-normal">Обозначение</th>
                <th className="text-left px-4 py-2.5 font-normal">Описание</th>
                <th className="text-left px-4 py-2.5 font-normal w-32">Значение</th>
                <th className="text-left px-4 py-2.5 font-normal w-24">Ед. изм.</th>
              </tr>
            </thead>
            <tbody>
              {spec.input_data.map((item, i) => (
                <tr key={item.id} className="border-b border-slate-700/50 hover:bg-navy/30">
                  <td className="px-4 py-2">
                    <input
                      value={item.symbol}
                      onChange={e => updateInput(i, 'symbol', e.target.value)}
                      className="bg-transparent border border-transparent hover:border-slate-600 focus:border-accent
                        rounded px-2 py-1 w-full outline-none text-slate-200 text-xs font-mono"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      value={item.description}
                      onChange={e => updateInput(i, 'description', e.target.value)}
                      className="bg-transparent border border-transparent hover:border-slate-600 focus:border-accent
                        rounded px-2 py-1 w-full outline-none text-slate-300 text-xs"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      value={item.value}
                      onChange={e => updateInput(i, 'value', e.target.value)}
                      className="bg-transparent border border-transparent hover:border-slate-600 focus:border-accent
                        rounded px-2 py-1 w-full outline-none text-accent text-xs font-mono"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      value={item.unit}
                      onChange={e => updateInput(i, 'unit', e.target.value)}
                      className="bg-transparent border border-transparent hover:border-slate-600 focus:border-accent
                        rounded px-2 py-1 w-full outline-none text-slate-500 text-xs"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Sections */}
      {spec.sections.map((sec, si) => {
        const open = openSections.has(sec.id)
        return (
          <div key={sec.id} className="bg-navy-light border border-slate-700 rounded-xl mb-4 overflow-hidden">
            <button
              onClick={() => toggleSection(sec.id)}
              className="w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-navy/30 transition-colors"
            >
              {open ? <ChevronDown size={16} className="text-slate-500" /> : <ChevronRight size={16} className="text-slate-500" />}
              <span className="font-semibold text-slate-200">{sec.title}</span>
              <span className="text-xs text-slate-500 ml-auto">{sec.steps.length} шагов</span>
            </button>

            {open && (
              <div className="border-t border-slate-700 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-500 border-b border-slate-700">
                      <th className="text-left px-4 py-2 font-normal w-24">Символ</th>
                      <th className="text-left px-4 py-2 font-normal">Описание</th>
                      <th className="text-left px-4 py-2 font-normal">Формула</th>
                      <th className="text-left px-4 py-2 font-normal w-20">Ед. изм.</th>
                      <th className="text-left px-4 py-2 font-normal w-16">Округл.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sec.steps.map((step, ti) => (
                      <tr key={step.id} className="border-b border-slate-700/50 hover:bg-navy/30">
                        <td className="px-4 py-2 font-mono text-xs text-accent">{step.result_symbol}</td>
                        <td className="px-4 py-2">
                          <input
                            value={step.description}
                            onChange={e => updateStep(si, ti, 'description', e.target.value)}
                            className="bg-transparent border border-transparent hover:border-slate-600 focus:border-accent
                              rounded px-2 py-1 w-full outline-none text-slate-300 text-xs"
                          />
                        </td>
                        <td className="px-4 py-2">
                          <input
                            value={step.formula}
                            onChange={e => updateStep(si, ti, 'formula', e.target.value)}
                            className="bg-transparent border border-transparent hover:border-slate-600 focus:border-accent
                              rounded px-2 py-1 w-full outline-none text-slate-200 text-xs font-mono"
                          />
                        </td>
                        <td className="px-4 py-2">
                          <input
                            value={step.unit}
                            onChange={e => updateStep(si, ti, 'unit', e.target.value)}
                            className="bg-transparent border border-transparent hover:border-slate-600 focus:border-accent
                              rounded px-2 py-1 w-full outline-none text-slate-500 text-xs"
                          />
                        </td>
                        <td className="px-4 py-2 text-xs text-slate-500 text-center">{step.rounding}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
