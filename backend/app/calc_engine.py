"""
Расчётный движок.

Идея: проходим по spec.input_data и заносим значения в окружение
(namespace) asteval. Затем последовательно по spec.sections / steps
вычисляем formula каждого шага в этом окружении и сохраняем результат
обратно в namespace под именем step.id, чтобы следующие шаги могли
на него ссылаться.

Табличная интерполяция доступна внутри формул как interp('table_id', x).
"""
from __future__ import annotations

from typing import Dict

from asteval import Interpreter

from .schemas import CalculationSpec


class CalcError(Exception):
    def __init__(self, step_id: str, message: str):
        super().__init__(f"Ошибка в шаге '{step_id}': {message}")
        self.step_id = step_id


def _make_interp_function(tables_by_id: Dict[str, "TableDef"]):  # noqa: F821
    def interp(table_id: str, x: float) -> float:
        table = tables_by_id.get(table_id)
        if table is None:
            raise ValueError(f"Таблица '{table_id}' не найдена в спецификации")

        xs, ys = table.x, table.y
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]

        for i in range(len(xs) - 1):
            x0, x1 = xs[i], xs[i + 1]
            if x0 <= x <= x1:
                y0, y1 = ys[i], ys[i + 1]
                if x1 == x0:
                    return y0
                t = (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)

        return ys[-1]

    return interp


def run_calculation(spec: CalculationSpec) -> Dict[str, float]:
    """
    Возвращает плоский словарь {id: значение} — все input_data и все
    результаты шагов. Также мутирует spec.sections[*].steps[*].value
    (для удобства последующей генерации документа).
    """
    aeval = Interpreter()

    # 1. Загружаем входные данные в namespace
    results: Dict[str, float] = {}
    for item in spec.input_data:
        try:
            value = float(item.value)
        except (TypeError, ValueError):
            # value может быть выражением-строкой в редких случаях —
            # пробуем вычислить его в текущем (уже частично заполненном)
            # namespace.
            value = aeval.eval(str(item.value))
            if aeval.error:
                raise CalcError(item.id, f"не удалось вычислить input_data: {item.value}")

        aeval.symtable[item.id] = value
        results[item.id] = value

    # 2. Регистрируем функцию interp с доступом к таблицам спецификации
    tables_by_id = {t.id: t for t in spec.tables}
    aeval.symtable["interp"] = _make_interp_function(tables_by_id)

    # 3. Последовательно считаем шаги
    for section in spec.sections:
        for step in section.steps:
            aeval.error = []
            value = aeval.eval(step.formula)

            if aeval.error:
                error_msgs = "; ".join(str(e.get_error()) for e in aeval.error)
                raise CalcError(step.id, f"{step.formula!r} -> {error_msgs}")

            try:
                value = float(value)
            except (TypeError, ValueError):
                raise CalcError(step.id, f"формула вернула не число: {value!r}")

            aeval.symtable[step.id] = value
            step.value = value
            results[step.id] = value

    return results
