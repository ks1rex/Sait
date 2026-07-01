const cfg: Record<string, { label: string; cls: string }> = {
  pending:    { label: 'Ожидание',   cls: 'bg-slate-700 text-slate-300' },
  extracting: { label: 'Извлечение', cls: 'bg-yellow-900 text-yellow-300' },
  extracted:  { label: 'Готово',     cls: 'bg-blue-900 text-blue-300' },
  computing:  { label: 'Расчёт',     cls: 'bg-yellow-900 text-yellow-300' },
  computed:   { label: 'Вычислено',  cls: 'bg-blue-900 text-blue-300' },
  generating: { label: 'Генерация',  cls: 'bg-purple-900 text-purple-300' },
  done:       { label: 'Готово',     cls: 'bg-green-900 text-green-300' },
  error:      { label: 'Ошибка',     cls: 'bg-red-900 text-red-300' },
}

export function StatusBadge({ status }: { status: string }) {
  const { label, cls } = cfg[status] ?? { label: status, cls: 'bg-slate-700 text-slate-300' }
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{label}</span>
}
