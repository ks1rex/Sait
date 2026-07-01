import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'

interface Props {
  label: string
  accept: string
  file: File | null
  onChange: (f: File | null) => void
  required?: boolean
}

export function FileDropZone({ label, accept, file, onChange, required }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onChange(f)
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center gap-2 cursor-pointer transition-colors
        ${dragging ? 'border-accent bg-accent/10' : 'border-slate-600 hover:border-accent/60 bg-navy-light'}`}
    >
      <Upload size={28} className={file ? 'text-accent' : 'text-slate-500'} />
      <span className="text-sm text-slate-400 text-center">
        {file ? (
          <span className="text-accent font-medium">{file.name}</span>
        ) : (
          <>
            <span className="text-slate-300">{label}</span>
            {required && <span className="text-red-400 ml-1">*</span>}
            <br />
            <span className="text-xs">Перетащите файл или нажмите</span>
          </>
        )}
      </span>
      {file && (
        <button
          type="button"
          onClick={e => { e.stopPropagation(); onChange(null) }}
          className="text-xs text-slate-500 hover:text-red-400 mt-1"
        >
          Удалить
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={e => onChange(e.target.files?.[0] ?? null)}
      />
    </div>
  )
}
