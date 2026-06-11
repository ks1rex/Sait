"""
Lokal'nyy test: calc_engine -> docx_generator -> soffice PDF.
Zapusk: cd backend && venv/Scripts/python test_generate.py
Rezul'tat sohranyayetsya v ../test_output/.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

# ── пути ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent          # корень репозитория
OUT_DIR = ROOT / "test_output"
OUT_DIR.mkdir(exist_ok=True)

DOCX_PATH = str(OUT_DIR / "test_report.docx")
PDF_PATH  = str(OUT_DIR / "test_report.pdf")

SOFFICE = os.getenv(
    "LIBREOFFICE_PATH",
    "C:/Program Files/LibreOffice/program/soffice.exe",
)

# ── spec ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.schemas import CalculationSpec, InputDatum, Section, Step
from app.calc_engine import run_calculation
from app.docx_generator import generate_docx

spec = CalculationSpec(
    title="Расчёт системы водоснабжения малого посёлка",
    discipline="Водоснабжение и водоотведение",
    work_type="курсовая работа",
    input_data=[
        InputDatum(
            id="Q_sut", symbol="Qсут", value=3600,
            unit="м³/сут", description="Среднесуточный расход воды",
        ),
        InputDatum(
            id="K_max_ch", symbol="Kmax.ч", value=1.7,
            unit="", description="Коэффициент максимальной часовой неравномерности",
        ),
        InputDatum(
            id="v_ek", symbol="vэк", value=1.0,
            unit="м/с", description="Экономическая скорость движения воды в трубах",
        ),
        InputDatum(
            id="H_sv", symbol="Hсв", value=10.0,
            unit="м", description="Свободный напор в распределительной сети",
        ),
        InputDatum(
            id="l_pipe", symbol="l", value=500,
            unit="м", description="Длина расчётного участка трубопровода",
        ),
        InputDatum(
            id="i_hydr", symbol="i", value=0.005,
            unit="м/м", description="Гидравлический уклон",
        ),
    ],
    tables=[],
    sections=[
        Section(
            id="section_1",
            title="1. Определение расчётных расходов воды",
            intro_text=(
                "Определение средних и максимальных расходов воды "
                "в системе водоснабжения."
            ),
            steps=[
                Step(
                    id="Q_chas",
                    result_symbol="Qч",
                    description="Средний часовой расход воды",
                    formula="Q_sut / 24",
                    unit="м³/ч",
                    rounding=3,
                    depends_on=["Q_sut"],
                ),
                Step(
                    id="Q_sek",
                    result_symbol="Qс",
                    description="Средний секундный расход воды",
                    formula="Q_sut * 1000 / 86400",
                    unit="л/с",
                    rounding=3,
                    depends_on=["Q_sut"],
                ),
                Step(
                    id="Q_max_chas",
                    result_symbol="Qmax.ч",
                    description="Максимальный часовой расход воды",
                    formula="Q_chas * K_max_ch",
                    unit="м³/ч",
                    rounding=3,
                    depends_on=["Q_chas", "K_max_ch"],
                ),
                Step(
                    id="Q_max_sek",
                    result_symbol="Qmax.с",
                    description="Максимальный секундный расход воды",
                    formula="Q_max_chas * 1000 / 3600",
                    unit="л/с",
                    rounding=3,
                    depends_on=["Q_max_chas"],
                ),
            ],
        ),
        Section(
            id="section_2",
            title="2. Гидравлический расчёт трубопровода",
            intro_text="Подбор диаметра трубопровода и определение требуемого напора.",
            steps=[
                Step(
                    id="D_raschet",
                    result_symbol="Dрасч",
                    description="Расчётный диаметр трубопровода",
                    formula="sqrt(4 * Q_max_sek / (1000 * pi * v_ek))",
                    unit="м",
                    rounding=4,
                    explanation=(
                        "Диаметр определяется из условия обеспечения экономической "
                        "скорости. Q переведён из л/с в м³/с делением на 1000."
                    ),
                    depends_on=["Q_max_sek", "v_ek"],
                ),
                Step(
                    id="D_mm",
                    result_symbol="D",
                    description="Диаметр трубопровода",
                    formula="D_raschet * 1000",
                    unit="мм",
                    rounding=1,
                    depends_on=["D_raschet"],
                ),
                Step(
                    id="h_poteri",
                    result_symbol="h",
                    description="Потери напора на расчётном участке",
                    formula="i_hydr * l_pipe",
                    unit="м",
                    rounding=3,
                    depends_on=["i_hydr", "l_pipe"],
                ),
                Step(
                    id="H_nasos",
                    result_symbol="Hнас",
                    description="Требуемый напор насосной станции",
                    formula="h_poteri + H_sv",
                    unit="м",
                    rounding=2,
                    depends_on=["h_poteri", "H_sv"],
                ),
            ],
        ),
    ],
    conclusion_instructions=(
        "Указать итоговые расчётные расходы воды (средний и максимальный секундный). "
        "Привести принятый диаметр трубопровода и требуемый напор насосной станции. "
        "Сделать вывод о соответствии скоростного режима нормативным требованиям СП 31.13330."
    ),
)

META = {
    "university": "Уральский государственный технический университет",
    "student_name": "Иванов И.И.",
    "group": "ВВ-301",
    "supervisor": "Петрова А.С.",
    "city_year": "Екатеринбург, 2026",
}

# ── расчёт ───────────────────────────────────────────────────────────────────
print("--- Raschet ---")
results = run_calculation(spec)

EXPECTED = {
    "Q_chas":     3600 / 24,              # 150.0
    "Q_sek":      3600 * 1000 / 86400,    # ≈ 41.667
    "Q_max_chas": 150 * 1.7,              # 255.0
    "Q_max_sek":  255 * 1000 / 3600,      # ≈ 70.833
    "D_raschet":  math.sqrt(4 * (255*1000/3600) / (1000 * math.pi * 1.0)),
    "D_mm":       math.sqrt(4 * (255*1000/3600) / (1000 * math.pi * 1.0)) * 1000,
    "h_poteri":   0.005 * 500,            # 2.5
    "H_nasos":    2.5 + 10.0,             # 12.5
}

ok = True
for key, expected in EXPECTED.items():
    got = results.get(key)
    match = abs(got - expected) < 1e-6 if got is not None else False
    status = "OK" if match else "FAIL"
    print(f"  [{status}]  {key:15s}  expected={expected:.6f}   got={got:.6f}")
    if not match:
        ok = False

if ok:
    print("\nAll values match expected.\n")
else:
    print("\nMISMATCH -- check formulas.\n")
    sys.exit(1)

# добавляем заключение вручную (без AI)
spec.conclusion_text = (
    "В результате выполненного расчёта системы водоснабжения малого посёлка "
    "определены расчётные расходы воды: средний секундный расход составляет "
    f"{results['Q_sek']:.3f} л/с, максимальный секундный — "
    f"{results['Q_max_sek']:.3f} л/с. "
    f"Расчётный диаметр трубопровода составляет {results['D_raschet']:.4f} м "
    f"({results['D_mm']:.1f} мм). "
    f"Потери напора на участке длиной {int(results['l_pipe'])} м — "
    f"{results['h_poteri']:.3f} м, требуемый напор насосной станции — "
    f"{results['H_nasos']:.2f} м. "
    "Скоростной режим соответствует нормативным требованиям СП 31.13330."
)

# ── генерация docx ───────────────────────────────────────────────────────────
print("--- Generatsiya .docx ---")
generate_docx(spec, META, DOCX_PATH)
print(f"   Saved: {DOCX_PATH}")

# ── конвертация в PDF ────────────────────────────────────────────────────────
print("--- Konvertatsiya v PDF ---")
if not os.path.exists(SOFFICE):
    print(f"   soffice not found: {SOFFICE}")
    print("   Install LibreOffice or set LIBREOFFICE_PATH in .env")
    sys.exit(0)

try:
    proc = subprocess.run(
        [SOFFICE, "--headless", "--convert-to", "pdf",
         "--outdir", str(OUT_DIR), DOCX_PATH],
        check=True,
        capture_output=True,
        timeout=90,
    )
    if os.path.exists(PDF_PATH):
        size_kb = os.path.getsize(PDF_PATH) // 1024
        print(f"   Saved: {PDF_PATH}  ({size_kb} KB)")
    else:
        print("   soffice finished OK but no PDF was created.")
        print(proc.stdout.decode(errors="replace"))
except subprocess.CalledProcessError as e:
    print("   LibreOffice error:", e.stderr.decode(errors="replace")[:400])
except subprocess.TimeoutExpired:
    print("   Conversion timeout (90s)")

print("\nDone. Files in:", OUT_DIR)
