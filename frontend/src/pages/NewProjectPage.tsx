import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileDropZone } from '../components/FileDropZone'
import { useToast } from '../components/Toast'
import { apiPostForm } from '../lib/api'

interface UploadResponse { project_id: string }
interface ExtractResponse { status: string }

export function NewProjectPage() {
  const [taskFile, setTaskFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<'idle' | 'uploading' | 'extracting'>('idle')
  const toast = useToast()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!taskFile) { toast('Выберите файл задания', 'error'); return }

    setLoading(true)
    try {
      setStep('uploading')
      const form = new FormData()
      form.append('task', taskFile)
      form.append('generation_mode', 'universal')
      const { project_id } = await apiPostForm<UploadResponse>('/upload', form)

      setStep('extracting')
      await apiPostForm<ExtractResponse>(`/extract?project_id=${project_id}`, new FormData())

      navigate(`/project/${project_id}/review`)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Ошибка загрузки', 'error')
      setStep('idle')
    } finally {
      setLoading(false)
    }
  }

  const stepLabel: Record<string, string> = {
    idle: 'Создать проект',
    uploading: 'Загрузка файла...',
    extracting: 'Извлечение данных (ИИ)...',
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-100 mb-2">Новый расчётный проект</h1>
      <p className="text-sm text-slate-400 mb-8">
        Загрузите PDF с заданием — ИИ извлечёт структуру, формулы и исходные данные.
        Вы сможете проверить и отредактировать спецификацию перед расчётом.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <FileDropZone
          label="Файл задания (PDF)"
          accept=".pdf"
          file={taskFile}
          onChange={setTaskFile}
          required
        />

        {taskFile && (
          <div className="bg-navy-light border border-slate-700 rounded-xl p-4 text-sm text-slate-400">
            <p className="font-medium text-slate-300 mb-1">Что будет дальше:</p>
            <ol className="list-decimal list-inside space-y-1">
              <li>ИИ проанализирует задание и извлечёт спецификацию</li>
              <li>Вы проверите и при необходимости скорректируете данные</li>
              <li>Система выполнит расчёты и сформирует отчёт по ГОСТ</li>
            </ol>
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !taskFile}
          className="py-3 rounded-xl bg-accent hover:bg-accent-dark text-white font-medium text-sm
            transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {stepLabel[step]}
        </button>
      </form>
    </div>
  )
}
