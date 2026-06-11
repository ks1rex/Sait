"""
Pydantic-модели, отражающие docs/calculation_spec_schema.json.
Используются для валидации JSON, который вернул DeepSeek, и как
типы данных для calc_engine.py / docx_generator.py.
"""
from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, Field


class InputDatum(BaseModel):
    id: str
    symbol: str
    value: Union[float, int, str]
    unit: str = ""
    description: str = ""


class TableDef(BaseModel):
    id: str
    name: str
    x: List[float]
    y: List[float]
    x_label: str = ""
    y_label: str = ""
    interpolation: str = "linear"


class Step(BaseModel):
    id: str
    result_symbol: str
    description: str
    formula: str
    unit: str = ""
    rounding: int = 3
    explanation: str = ""
    depends_on: List[str] = Field(default_factory=list)

    # Заполняется после расчёта (calc_engine.py)
    value: Optional[float] = None


class Section(BaseModel):
    id: str
    title: str
    intro_text: str = ""
    steps: List[Step] = Field(default_factory=list)


class CalculationSpec(BaseModel):
    title: str
    discipline: str = ""
    work_type: str = ""
    input_data: List[InputDatum]
    tables: List[TableDef] = Field(default_factory=list)
    sections: List[Section]
    conclusion_instructions: str = ""

    # Заполняется после генерации (docx_generator.py)
    conclusion_text: Optional[str] = None
