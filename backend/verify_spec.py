"""Temporary check: validate the vodootvedenie spec and compare engine
results against the reference coursework numbers."""
import json
import sys

from app.schemas import CalculationSpec
from app.calc_engine import run_calculation

SPEC_PATH = "templates/specs/vodootvedenie_ochistnye_sooruzheniya.json"

# (step_id, reference value from the etalon document, abs tolerance)
REFERENCE = [
    ("Q_sr_chas", 1666.67, 0.01),
    ("Q_sr_sek", 0.463, 0.001),
    ("K_max", 1.5093, 0.0005),
    ("q_max_chas", 2515.501, 1.0),
    ("q_max_sek", 0.699, 0.001),
    ("K_min", 0.6526, 0.0005),
    ("q_min_chas", 1087.667, 1.0),
    ("q_min_sek", 0.302, 0.001),
    ("v_r_ms", 0.741, 0.001),
    ("L_f_m", 7000, 0.1),
    ("Q_r_m3s", 35, 0.01),
    ("fi", 1.207, 0.001),
    ("E_dif", 0.005187, 0.00001),
    ("alpha", 0.27, 0.001),
    ("a_smesh", 0.694, 0.002),
    ("n_razb", 53.462, 0.2),
    ("b_r_gm3", 12.7, 0.001),
    ("b_vh", 26.066, 0.05),
    ("E_b", 87.53, 0.05),
    ("L_r_gm3", 2.213, 0.001),
    ("T_sek", 9447, 5),
    ("T_sut", 0.109, 0.001),
    # The etalon computed L_vh with rounded intermediates (a=0.694, T=0.109);
    # full-precision propagation gives ~52.72, downstream values still match.
    ("L_vh", 52.654, 0.1),
    ("E_L", 84.04, 0.05),
    ("O_r_gm3", 5.096, 0.001),
    ("L_vh_O2", 37.648, 0.05),
    ("E_O2", 88.59, 0.05),
    ("n_resh", 160, 0),
    ("B_r", 3.4176, 0.001),
    ("L1_resh", 4.178, 0.01),
    ("L2_resh", 2.089, 0.01),
    ("L_resh", 7.967, 0.02),
    ("dzeta_resh", 0.652, 0.001),
    ("h_p_resh", 0.081, 0.001),
    ("H_resh", 0.809, 0.001),
    ("omega_pes", 3.495, 0.005),
    ("H_pes", 1.87, 0.005),
    ("B_pes", 1.87, 0.005),
    ("h1_pes", 0.935, 0.005),
    ("k_pes", 2.62, 0.001),
    ("L_pes", 18.558, 0.02),
    ("H_k_pes", 2.086, 0.005),
    ("Q_pes", 258.194, 0.5),
    ("T_per_sek", 1800, 0),
    ("u0_per", 0.631, 0.001),
    ("u0_per_ms", 0.000631, 0.000001),
    ("u_per_ms", 0.0, 0.0000001),
    ("q_set_per", 0.0722, 0.0002),
    ("n_per", 10, 0),
    ("rho_aer", 10.588, 0.01),
    ("t_sm_aer", 6.452, 0.01),
    ("W_aer", 10753.33, 10),
    ("R_i_aer", 0.684, 0.001),
    ("a_r_aer", 7.028, 0.01),
    ("t_o_aer", 5.449, 0.01),
    ("H1_vtor_m", 2.72, 0.001),
    ("q_vtor", 1.131, 0.002),
    ("S_vtor", 2224.139, 3),
    ("D_rasch_vtor", 23.8, 0.1),
    ("q_h_chas", 7.547, 0.01),
    ("q_h_sut", 181.12, 0.2),
    ("V_hl", 1257.75, 1.5),
    ("T_hl_sek", 1800, 0),
    ("v_hl_ms", 0.0062, 0.0001),
    ("L_hl", 11.16, 0.02),
    ("omega_hl", 112.7, 0.3),
    ("T_hl_min", 30, 0),
]


def main() -> int:
    with open(SPEC_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    spec = CalculationSpec.model_validate(raw)
    print(f"OK: spec validates against CalculationSpec "
          f"({len(spec.input_data)} inputs, {len(spec.tables)} tables, "
          f"{sum(len(s.steps) for s in spec.sections)} steps "
          f"in {len(spec.sections)} sections)")

    results = run_calculation(spec)
    print("OK: calc_engine ran all steps without errors")

    # Jinja2 templates: every {{ id }} must exist among results
    import re
    missing = []
    for field in ("intro_text_template", "conclusion_text_template"):
        tpl = raw.get(field) or ""
        for var in re.findall(r"\{\{\s*([A-Za-z_][A-Za-z_0-9]*)\s*\}\}", tpl):
            if var not in results:
                missing.append((field, var))
    if missing:
        print("FAIL: template vars missing from results:", missing)
    else:
        print("OK: all template variables resolve to computed/input ids")

    failures = []
    for step_id, ref, tol in REFERENCE:
        got = results.get(step_id)
        if got is None:
            failures.append((step_id, ref, "MISSING"))
            continue
        if abs(got - ref) > tol:
            failures.append((step_id, ref, got))

    if failures:
        print(f"\n{len(failures)} mismatches (id, reference, computed):")
        for step_id, ref, got in failures:
            print(f"  {step_id:>14}: ref={ref}  got={got}")
    else:
        print(f"OK: all {len(REFERENCE)} reference numbers match within tolerance")

    return 1 if (failures or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
