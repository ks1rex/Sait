"""Проверка имён переменных и формул (app/calc_engine.py::validate_spec).

Запуск: python test_validate_spec.py
"""
from app.calc_engine import CalcError, run_calculation
from app.schemas import CalculationSpec


def spec(inputs, steps):
    return CalculationSpec.model_validate({
        "title": "t",
        "input_data": [{"id": i, "symbol": i, "value": v} for i, v in inputs],
        "sections": [{"id": "s1", "title": "s", "steps": [
            {"id": i, "result_symbol": i, "description": i, "formula": f} for i, f in steps
        ]}],
    })


def fails(s) -> str:
    try:
        run_calculation(s)
    except CalcError as exc:
        return str(exc)
    raise AssertionError("ожидалась ошибка, но расчёт прошёл")


# Кириллица в именах и формулах считается
res = run_calculation(spec([("Qсут", 2400), ("Кмакс", 1.5)], [("Qср_час", "Qсут / 24"), ("qmax", "Qср_час * Кмакс")]))
assert res["qmax"] == 150.0, res

# Латинская K вместо русской К — ошибка с подсказкой, а не «name is not defined»
msg = fails(spec([("Кмакс", 1.5)], [("q", "Kмакс * 2")]))
assert "неизвестная переменная 'Kмакс'" in msg and "'Кмакс'" in msg, msg

# Формула ссылается на обозначение, которого нет среди переменных (реальный баг)
msg = fails(spec([("Q_sut", 2400)], [("Q_sr_chas", "Q_сут/24")]))
assert "неизвестная переменная 'Q_сут'" in msg and "Q_sut" in msg, msg

# Недопустимое имя
msg = fails(spec([("Q сут", 1)], [("y", "1 + 1")]))
assert "недопустимое имя переменной" in msg, msg

# Дубликат имени
msg = fails(spec([("Q", 1), ("Q", 2)], [("y", "Q")]))
assert "объявлена дважды" in msg, msg

# Синтаксическая ошибка в формуле
msg = fails(spec([("Q", 1)], [("y", "Q / ")]))
assert "записана с ошибкой" in msg, msg

# Порядок шагов может быть любым (forward-reference)
res = run_calculation(spec([("Q", 24)], [("b", "a * 2"), ("a", "Q / 24")]))
assert res["b"] == 2.0, res

print("OK")
