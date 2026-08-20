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

import ast
import difflib
import keyword
import unicodedata
from typing import Dict

from asteval import Interpreter
from jinja2.sandbox import SandboxedEnvironment

from .schemas import CalculationSpec

# Text templates (intro/conclusion) can be edited by end users via PUT /spec,
# so they are untrusted. A raw jinja2.Template would allow SSTI → RCE
# (e.g. {{ cycler.__init__.__globals__ ... }}). SandboxedEnvironment blocks
# access to dunders / unsafe attributes while still supporting {{ var }}.
_sandbox = SandboxedEnvironment(autoescape=False)


class CalcError(Exception):
    def __init__(self, step_id: str, message: str):
        super().__init__(f"Ошибка в шаге '{step_id}': {message}")
        self.step_id = step_id


# Имена, доступные в формулах помимо переменных спецификации.
_BUILTIN_NAMES: frozenset[str] = frozenset({
    'sqrt', 'exp', 'log', 'log10', 'log2', 'sin', 'cos', 'tan', 'asin', 'acos',
    'atan', 'atan2', 'sinh', 'cosh', 'tanh', 'degrees', 'radians',
    'ceil', 'floor', 'abs', 'round', 'min', 'max', 'sum', 'pow',
    'pi', 'e', 'inf', 'True', 'False', 'None', 'interp',
})


def _names_in_formula(formula: str) -> set[str]:
    """Имена переменных, реально прочитанные Python-парсером из формулы.

    Берём именно ast, а не регулярку: парсер нормализует идентификаторы
    (NFKC) ровно так же, как это потом сделает asteval, — иначе проверка
    расходилась бы с расчётом.
    """
    tree = ast.parse(formula.strip(), mode='eval')
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _check_name(name: str, where: str, step_id: str) -> None:
    """Имя переменной должно быть валидным идентификатором Python.

    Кириллица разрешена (Qсут, К_макс) — запрещены пробелы, точки, запятые,
    знаки и совпадения с ключевыми словами/функциями.
    """
    if not name or not name.isidentifier() or keyword.iskeyword(name):
        raise CalcError(
            step_id,
            f"недопустимое имя переменной '{name}' ({where}): разрешены буквы "
            "(латиница и кириллица), цифры и «_», имя не может начинаться с цифры "
            "и содержать пробелы, точки, запятые или знаки",
        )
    if unicodedata.normalize('NFKC', name) != name:
        raise CalcError(
            step_id,
            f"имя переменной '{name}' ({where}) содержит нестандартные символы "
            "(индексы, спецбуквы) — замените их обычными буквами или цифрами",
        )
    if name in _BUILTIN_NAMES:
        raise CalcError(
            step_id,
            f"имя переменной '{name}' ({where}) совпадает со встроенной функцией — "
            "переименуйте переменную",
        )


def validate_spec(spec: CalculationSpec) -> None:
    """Проверить имена переменных и формулы ДО расчёта.

    Без этого любая опечатка (в т.ч. латинская 'K' вместо русской 'К')
    всплывала в виде «неизвестная переменная» уже на /compute у пользователя.
    """
    known: set[str] = set()

    for item in spec.input_data:
        _check_name(item.id, 'исходные данные', item.id)
        if item.id in known:
            raise CalcError(item.id, f"переменная '{item.id}' объявлена дважды")
        known.add(item.id)

    for section in spec.sections:
        for step in section.steps:
            _check_name(step.id, f"шаг «{step.description or step.id}»", step.id)
            if step.id in known:
                raise CalcError(step.id, f"переменная '{step.id}' объявлена дважды")
            known.add(step.id)

    for section in spec.sections:
        for step in section.steps:
            if not step.formula.strip():
                raise CalcError(step.id, "формула пустая")
            try:
                names = _names_in_formula(step.formula)
            except SyntaxError as exc:
                raise CalcError(
                    step.id,
                    f"формула {step.formula!r} записана с ошибкой: {exc.msg}",
                )
            for name in sorted(names - known - _BUILTIN_NAMES):
                hint = difflib.get_close_matches(name, sorted(known), n=1, cutoff=0.6)
                raise CalcError(
                    step.id,
                    f"в формуле {step.formula!r} используется неизвестная переменная "
                    f"'{name}'"
                    + (
                        f" — возможно, имелась в виду '{hint[0]}' (проверьте раскладку: "
                        "русские и латинские буквы выглядят одинаково)"
                        if hint
                        else "; доступные переменные: " + ", ".join(sorted(known)[:30])
                    ),
                )


def _make_interp_function(tables_by_id: Dict[str, "TableDef"]):  # noqa: F821
    def interp(table_id: str, x: float) -> float:
        table = tables_by_id.get(table_id)
        if table is None:
            raise ValueError(f"Таблица '{table_id}' не найдена в спецификации")

        xs, ys = table.x, table.y
        if not xs or not ys:
            raise ValueError(f"Таблица '{table_id}' пуста (нет точек x/y)")
        if len(xs) != len(ys):
            raise ValueError(
                f"Таблица '{table_id}': разная длина столбцов x ({len(xs)}) и y ({len(ys)})"
            )
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


def _eval_step(aeval: Interpreter, step) -> tuple[float | None, list[str]]:
    """
    Evaluate one step's formula. Returns (value, error_types).
    error_types is a list of asteval error class names (empty on success).
    """
    aeval.error = []
    value = aeval.eval(step.formula, show_errors=False)
    if aeval.error:
        return None, [e.get_error()[0] for e in aeval.error]
    return value, []


def run_calculation(spec: CalculationSpec) -> Dict[str, float]:
    """
    Возвращает плоский словарь {id: значение} — все input_data и все
    результаты шагов. Также мутирует spec.sections[*].steps[*].value
    (для удобства последующей генерации документа).

    Порядок вычисления: шаги считаются в порядке из spec, но если шаг
    ссылается на ещё не определённую переменную (forward-reference из-за
    неидеального порядка от AI), он откладывается и повторяется в следующем
    проходе. Так корректно упорядоченные spec считаются за один проход
    идентично прежнему поведению, а слегка переставленные — всё равно
    разрешаются по фактическим зависимостям (поле depends_on не требуется
    идеально заполненным). Реальные ошибки (деление на ноль, неизвестная
    функция) поднимаются сразу.
    """
    validate_spec(spec)

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

    # 3. Считаем шаги многопроходно по фактическим зависимостям
    pending = [step for section in spec.sections for step in section.steps]
    last_nameerror: Dict[str, str] = {}

    while pending:
        still_pending = []
        made_progress = False

        for step in pending:
            value, error_types = _eval_step(aeval, step)

            if error_types:
                # Чистый NameError → возможно forward-reference, отложим.
                if all(t == "NameError" for t in error_types):
                    last_nameerror[step.id] = "; ".join(
                        str(e.get_error()[1]) for e in aeval.error
                    )
                    still_pending.append(step)
                    continue
                # Любая другая ошибка — реальная, поднимаем сразу.
                msgs = "; ".join(str(e.get_error()[1]) for e in aeval.error)
                raise CalcError(step.id, f"{step.formula!r} -> {msgs}")

            try:
                value = float(value)
            except (TypeError, ValueError):
                raise CalcError(step.id, f"формула вернула не число: {value!r}")

            aeval.symtable[step.id] = value
            step.value = value
            results[step.id] = value
            made_progress = True

        if not made_progress:
            # Остались шаги с неразрешимыми переменными — реальная ошибка.
            step = still_pending[0]
            raise CalcError(
                step.id,
                f"{step.formula!r} -> {last_nameerror.get(step.id, 'неизвестная переменная')}",
            )

        pending = still_pending

    return results


def render_display_template(template_str: str, context: Dict[str, str]) -> str:
    """
    Render a {{ id }}-style Jinja2 template (sandboxed) against a pre-built
    string context. Shared by render_text_template (intro/conclusion) and
    docx_generator's per-step formula_display rendering.
    """
    return _sandbox.from_string(template_str).render(**context)


def render_text_template(
    template_str: str,
    spec: CalculationSpec,
    results: Dict[str, float],
) -> str:
    """
    Render a Jinja2 template, replacing {{ id }} with formatted numeric values.

    Step ids use their rounding setting; input_data ids default to 2 decimals.
    Decimal separator is a comma (ГОСТ style).
    """
    rounding_by_id: Dict[str, int] = {
        step.id: step.rounding
        for section in spec.sections
        for step in section.steps
    }

    def _fmt(val: float, decimals: int) -> str:
        return f"{val:.{decimals}f}".replace(".", ",")

    context = {
        var_id: _fmt(value, rounding_by_id.get(var_id, 2))
        for var_id, value in results.items()
    }

    return render_display_template(template_str, context)
