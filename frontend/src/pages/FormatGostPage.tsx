import { useState } from 'react'
import { FileText, Download } from 'lucide-react'
import { FileDropZone } from '../components/FileDropZone'
import { useToast } from '../components/Toast'
import { apiPostFormBlob, ApiError } from '../lib/api'

export function FormatGostPage() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { toast('Выберите файл', 'error'); return }

    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const { blob, filename } = await apiPostFormBlob('/format-gost', form)

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      toast('Файл отформатирован и скачан', 'success')
    } catch (err: unknown) {
      if (!(err instanceof ApiError && err.status === 402)) {
        toast(err instanceof Error ? err.message : 'Ошибка форматирования', 'error')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <FileText size={24} className="text-accent" />
        <h1 className="text-2xl font-bold text-slate-100">Форматирование по ГОСТ</h1>
      </div>
      <p className="text-sm text-slate-400 mb-8">
        Загрузите .docx файл — сервис применит стили ГОСТ (Times New Roman 14, 1.5 интервал,
        отступы) и вернёт отформатированный документ.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <FileDropZone
          label="Документ Word (.docx)"
          accept=".docx"
          file={file}
          onChange={setFile}
          required
        />

        {file && (
          <div className="bg-navy-light border border-slate-700 rounded-xl p-4 text-sm text-slate-400 space-y-1">
            <p>Будут применены стили ГОСТ Р 7.0.5:</p>
            <ul className="list-disc list-inside space-y-0.5 text-xs">
              <li>Times New Roman 14pt, выравнивание по ширине</li>
              <li>Отступ первой строки 1.25 см</li>
              <li>Межстрочный интервал 1.5</li>
              <li>Поля: левое 3 см, правое 1.5 см, верхнее и нижнее 2 см</li>
            </ul>
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !file}
          className="flex items-center justify-center gap-2 py-3 rounded-xl bg-accent hover:bg-accent-dark
            text-white font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            'Форматирование...'
          ) : (
            <>
              <Download size={16} />
              Форматировать и скачать
            </>
          )}
        </button>
      </form>
    </div>
  )
}
