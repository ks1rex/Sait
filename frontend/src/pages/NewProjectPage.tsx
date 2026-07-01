import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, Layers, FileEdit, Wand2, MessageSquare, ChevronRight } from 'lucide-react'
import { FileDropZone } from '../components/FileDropZone'
import { useToast } from '../components/Toast'
import { apiGet, apiPostForm, ApiError } from '../lib/api'
import type { TemplateInfo } from '../types'

type GenerationMode = 'universal' | 'fixed_template' | 'custom_template'
type SubMode = 'format_only' | 'minimal_edit' | 'chat'

interface UploadResponse { project_id: string }

// ── Mode cards ───────────────────────────────────────────────────────────────

// ── Token cost helpers ───────────────────────────────────────────────────────

function pluralTokens(n: number): string {
  if (n === 1) return '1 токен'
  if (n >= 2 && n <= 4) return `${n} токена`
  return `${n} токенов`
}

function CostBadge({ label }: { label: string }) {
  return (
    <span className="ml-auto shrink-0 text-xs text-yellow-400/80 bg-yellow-950/40 border border-yellow-900/50
      rounded-full px-2 py-0.5 font-medium whitespace-nowrap">
      {label}
    </span>
  )
}

// ── Mode / sub-mode definitions ──────────────────────────────────────────────

const MODES: { id: GenerationMode; icon: React.ReactNode; title: string; desc: string; cost: string | null }[] = [
  {
    id: 'universal',
    icon: <BookOpen size={22} />,
    title: 'Стандартная курсовая',
    desc: 'AI распознаёт задание и формулы автоматически',
    cost: pluralTokens(3),
  },
  {
    id: 'fixed_template',
    icon: <Layers size={22} />,
    title: 'По шаблону',
    desc: 'Готовая методика расчёта, вы вводите только свой вариант',
    cost: pluralTokens(2),
  },
  {
    id: 'custom_template',
    icon: <FileEdit size={22} />,
    title: 'Свой шаблон',
    desc: 'Загружаете собственный образец работы',
    cost: null, // shown per sub-mode
  },
]

const SUB_MODES: { id: SubMode; icon: React.ReactNode; title: string; desc: string; cost: string }[] = [
  {
    id: 'format_only',
    icon: <Wand2 size={16} />,
    title: 'Привести к ГОСТ',
    desc: 'Форматирует без изменения содержания, убирает оглавление',
    cost: pluralTokens(1),
  },
  {
    id: 'minimal_edit',
    icon: <FileEdit size={16} />,
    title: 'Адаптировать под новое условие',
    desc: 'AI переписывает расчёты по новому заданию, сохраняя структуру',
    cost: pluralTokens(5),
  },
  {
    id: 'chat',
    icon: <MessageSquare size={16} />,
    title: 'Через чат',
    desc: 'Интерактивное редактирование — давайте команды ассистенту',
    cost: '1 токен / сообщение',
  },
]

// ── Component ────────────────────────────────────────────────────────────────

export function NewProjectPage() {
  const [mode, setMode] = useState<GenerationMode>('universal')
  const [subMode, setSubMode] = useState<SubMode>('format_only')

  // universal / fixed_template
  const [taskFile, setTaskFile] = useState<File | null>(null)
  const [templates, setTemplates] = useState<TemplateInfo[]>([])
  const [templateId, setTemplateId] = useState<string>('')
  const [loadingTemplates, setLoadingTemplates] = useState(false)

  // custom_template files
  const [templateFile, setTemplateFile] = useState<File | null>(null) // образец
  const [taskFile2, setTaskFile2] = useState<File | null>(null)       // условие

  const [step, setStep] = useState<'idle' | 'uploading' | 'extracting'>('idle')
  const toast = useToast()
  const navigate = useNavigate()

  // Load template list when fixed_template is selected
  useEffect(() => {
    if (mode !== 'fixed_template') return
    setLoadingTemplates(true)
    apiGet<TemplateInfo[]>('/templates')
      .then(data => {
        setTemplates(data)
        if (data.length > 0) setTemplateId(data[0].id)
      })
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoadingTemplates(false))
  }, [mode, toast])

  const handleModeChange = (m: GenerationMode) => {
    setMode(m)
    setTaskFile(null)
    setTemplateFile(null)
    setTaskFile2(null)
  }

  const isReady = () => {
    if (mode === 'universal') return !!taskFile
    if (mode === 'fixed_template') return !!taskFile && !!templateId
    if (subMode === 'format_only') return !!templateFile
    if (subMode === 'minimal_edit') return !!templateFile && !!taskFile2
    return true // chat — оба файла опциональны
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isReady()) return

    const form = new FormData()
    form.append('generation_mode', mode)

    if (mode === 'universal') {
      form.append('task', taskFile!)
    } else if (mode === 'fixed_template') {
      form.append('task', taskFile!)
      form.append('template_id', templateId)
    } else {
      form.append('sub_mode', subMode)
      if (templateFile) form.append('template', templateFile)
      if (subMode === 'minimal_edit' && taskFile2) form.append('task', taskFile2)
      if (subMode === 'chat' && taskFile2) form.append('task', taskFile2)
    }

    try {
      setStep('uploading')
      const { project_id } = await apiPostForm<UploadResponse>('/upload', form)

      // chat → skip extract, go straight to chat screen
      if (mode === 'custom_template' && subMode === 'chat') {
        navigate(`/project/${project_id}/chat`)
        return
      }

      setStep('extracting')
      await apiPostForm('/extract?project_id=' + project_id, new FormData())

      // format_only / minimal_edit → result immediately (extract returns done)
      if (mode === 'custom_template') {
        navigate(`/project/${project_id}/result`)
      } else {
        navigate(`/project/${project_id}/review`)
      }
    } catch (err: unknown) {
      // 402 is handled globally by InsufficientTokensModal — skip toast
      if (!(err instanceof ApiError && err.status === 402)) {
        toast(err instanceof Error ? err.message : 'Ошибка', 'error')
      }
      setStep('idle')
    }
  }

  const stepLabel = { idle: 'Создать проект', uploading: 'Загрузка...', extracting: 'Анализ (ИИ)...' }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-100 mb-1">Новый проект</h1>
      <p className="text-sm text-slate-400 mb-8">Выберите режим генерации и загрузите файлы</p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">

        {/* ── Mode selection ── */}
        <section>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Режим генерации</p>
          <div className="grid gap-3">
            {MODES.map(m => (
              <button
                key={m.id}
                type="button"
                onClick={() => handleModeChange(m.id)}
                className={`flex items-start gap-4 p-4 rounded-xl border text-left transition-colors
                  ${mode === m.id
                    ? 'border-accent bg-accent/10 text-slate-100'
                    : 'border-slate-700 bg-navy-light text-slate-400 hover:border-slate-500 hover:text-slate-200'}`}
              >
                <span className={`mt-0.5 shrink-0 ${mode === m.id ? 'text-accent' : 'text-slate-500'}`}>
                  {m.icon}
                </span>
                <span className="flex flex-col gap-0.5 flex-1 min-w-0">
                  <span className="font-medium text-sm">{m.title}</span>
                  <span className="text-xs text-slate-500">{m.desc}</span>
                </span>
                {m.cost && <CostBadge label={m.cost} />}
                {mode === m.id && !m.cost && <ChevronRight size={16} className="text-accent mt-1 shrink-0" />}
              </button>
            ))}
          </div>
        </section>

        {/* ── fixed_template: template selector ── */}
        {mode === 'fixed_template' && (
          <section className="bg-navy-light border border-slate-700 rounded-xl p-4 flex flex-col gap-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Методика расчёта</p>
            {loadingTemplates ? (
              <p className="text-sm text-slate-400">Загрузка шаблонов...</p>
            ) : templates.length === 0 ? (
              <p className="text-sm text-slate-500">Нет доступных шаблонов на сервере</p>
            ) : (
              <select
                value={templateId}
                onChange={e => setTemplateId(e.target.value)}
                className="bg-navy border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100
                  focus:outline-none focus:border-accent transition-colors"
              >
                {templates.map(t => (
                  <option key={t.id} value={t.id}>
                    {t.title} {t.discipline ? `— ${t.discipline}` : ''}
                  </option>
                ))}
              </select>
            )}
          </section>
        )}

        {/* ── custom_template: sub-mode ── */}
        {mode === 'custom_template' && (
          <section>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Под-режим</p>
            <div className="grid gap-2">
              {SUB_MODES.map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSubMode(s.id)}
                  className={`flex items-start gap-3 p-3 rounded-lg border text-left transition-colors
                    ${subMode === s.id
                      ? 'border-accent/70 bg-accent/10 text-slate-100'
                      : 'border-slate-700 bg-navy text-slate-400 hover:border-slate-600 hover:text-slate-300'}`}
                >
                  <span className={`mt-0.5 shrink-0 ${subMode === s.id ? 'text-accent' : 'text-slate-500'}`}>
                    {s.icon}
                  </span>
                  <span className="flex flex-col gap-0.5 flex-1 min-w-0">
                    <span className="font-medium text-sm">{s.title}</span>
                    <span className="text-xs text-slate-500">{s.desc}</span>
                  </span>
                  <CostBadge label={s.cost} />
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ── File zones ── */}
        <section className="flex flex-col gap-3">
          <p className="text-xs text-slate-500 uppercase tracking-wider">Файлы</p>

          {/* universal */}
          {mode === 'universal' && (
            <FileDropZone
              label="Задание (PDF)"
              accept=".pdf"
              file={taskFile}
              onChange={setTaskFile}
              required
            />
          )}

          {/* fixed_template */}
          {mode === 'fixed_template' && (
            <FileDropZone
              label="Файл варианта (PDF)"
              accept=".pdf"
              file={taskFile}
              onChange={setTaskFile}
              required
            />
          )}

          {/* custom_template/format_only */}
          {mode === 'custom_template' && subMode === 'format_only' && (
            <FileDropZone
              label="Ваш документ — образец работы (docx или PDF)"
              accept=".docx,.pdf"
              file={templateFile}
              onChange={setTemplateFile}
              required
            />
          )}

          {/* custom_template/minimal_edit */}
          {mode === 'custom_template' && subMode === 'minimal_edit' && (
            <>
              <FileDropZone
                label="Образец готовой работы (docx или PDF)"
                accept=".docx,.pdf"
                file={templateFile}
                onChange={setTemplateFile}
                required
              />
              <FileDropZone
                label="Новое задание / вариант (PDF или TXT)"
                accept=".pdf,.txt"
                file={taskFile2}
                onChange={setTaskFile2}
                required
              />
            </>
          )}

          {/* custom_template/chat */}
          {mode === 'custom_template' && subMode === 'chat' && (
            <>
              <FileDropZone
                label="Образец работы — опционально (docx или PDF)"
                accept=".docx,.pdf"
                file={templateFile}
                onChange={setTemplateFile}
              />
              <FileDropZone
                label="Новое задание — опционально (PDF или TXT)"
                accept=".pdf,.txt"
                file={taskFile2}
                onChange={setTaskFile2}
              />
              <p className="text-xs text-slate-500 text-center">
                После создания откроется экран чата для интерактивного редактирования
              </p>
            </>
          )}
        </section>

        {/* ── Submit ── */}
        <button
          type="submit"
          disabled={step !== 'idle' || !isReady()}
          className="py-3 rounded-xl bg-accent hover:bg-accent-dark text-white font-medium text-sm
            transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {stepLabel[step]}
        </button>
      </form>
    </div>
  )
}
