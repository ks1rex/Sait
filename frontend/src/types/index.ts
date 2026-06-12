export interface InputDataItem {
  id: string
  symbol: string
  description: string
  value: number | string
  unit: string
}

export interface CalculationStep {
  id: string
  result_symbol: string
  description: string
  formula: string
  explanation: string | null
  unit: string
  rounding: number
  value: number | null
}

export interface Section {
  id: string
  title: string
  level: number
  intro_text: string | null
  steps: CalculationStep[]
}

export interface CalculationSpec {
  title: string
  discipline: string
  work_type: string | null
  intro_text: string | null
  intro_text_template: string | null
  conclusion_text: string | null
  conclusion_text_template: string | null
  conclusion_instructions: string | null
  input_data: InputDataItem[]
  tables: unknown[]
  sections: Section[]
  references: string[]
}

export interface Project {
  id: string
  title: string
  status: string
  generation_mode: string
  created_at: string
  output_docx_path: string | null
  output_pdf_path: string | null
}
