"""
End-to-end acceptance test for fixed_template flow.
Runs: GET /templates -> POST /upload -> POST /extract -> POST /compute -> POST /generate
Downloads the docx and checks key computed values against reference numbers.
"""
import json
import os
import sys
import time
import uuid

import httpx
from dotenv import load_dotenv
from jose import jwt as jose_jwt

load_dotenv()

BASE = "http://localhost:8000"
PDF_PATH = "templates/source_examples/vodootvedenie_example.pdf"
OUT_DIR = "acceptance_out"
os.makedirs(OUT_DIR, exist_ok=True)

JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]
TEST_USER_ID = str(uuid.uuid4())

# System has a SOCKS4 proxy at 10808 — disable env proxy detection
CLIENT = httpx.Client(trust_env=False, timeout=120)

# ---------------------------------------------------------------------------


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def ensure_test_user() -> str:
    """Create a test auth user (if not exists) and return their user_id."""
    c = httpx.Client(trust_env=False, timeout=30)
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

    # Try to create user via admin API
    r = c.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        headers=headers,
        json={
            "email": "acceptance-test@local.dev",
            "password": "acceptance-test-pw-9x!",
            "email_confirm": True,
        },
    )
    if r.status_code in (200, 201):
        user_id = r.json()["id"]
        print(f"Created test user: {user_id}")
        return user_id
    if r.status_code == 422 and "already" in r.text.lower():
        # User already exists — list and find it
        r2 = c.get(f"{SUPABASE_URL}/auth/v1/admin/users", headers=headers)
        for u in r2.json().get("users", []):
            if u.get("email") == "acceptance-test@local.dev":
                print(f"Reusing existing test user: {u['id']}")
                return u["id"]
    print(f"Could not create/find test user: HTTP {r.status_code} {r.text[:200]}")
    sys.exit(1)


def make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "email": "acceptance-test@local.dev",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def check(resp: httpx.Response, label: str) -> dict:
    if resp.status_code >= 400:
        print(f"\nFAIL [{label}] HTTP {resp.status_code}")
        try:
            print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
        except Exception:
            print(resp.text[:500])
        sys.exit(1)
    print(f"OK   [{label}] HTTP {resp.status_code}")
    return resp.json()


# ---------------------------------------------------------------------------


def main():
    user_id = ensure_test_user()
    token = make_token(user_id)
    print(f"Test user_id: {user_id}")

    # Wait for backend
    for attempt in range(20):
        try:
            r = CLIENT.get(f"{BASE}/health")
            if r.status_code == 200:
                print(f"Backend ready (attempt {attempt + 1})")
                break
        except Exception:
            time.sleep(1)
    else:
        print("Backend not responding after 20s — abort")
        sys.exit(1)

    # 1. GET /templates
    templates = check(CLIENT.get(f"{BASE}/templates", headers=H(token)), "GET /templates")
    print(f"     Templates: {[t['id'] for t in templates]}")
    assert any(t["id"] == "vodootvedenie_ochistnye_sooruzheniya" for t in templates), \
        "vodootvedenie template not found!"

    # 2. POST /upload
    with open(PDF_PATH, "rb") as f:
        upload_resp = check(
            CLIENT.post(
                f"{BASE}/upload",
                headers=H(token),
                data={
                    "generation_mode": "fixed_template",
                    "template_id": "vodootvedenie_ochistnye_sooruzheniya",
                },
                files={"task": ("vodootvedenie_example.pdf", f, "application/pdf")},
            ),
            "POST /upload",
        )
    project_id = upload_resp["project_id"]
    print(f"     project_id: {project_id}")
    print(f"     task_text_length: {upload_resp['task_text_length']}")

    # 3. POST /extract  (AI call — may take 30-60 s)
    print("     Calling /extract (AI, please wait)...")
    extract_resp = check(
        CLIENT.post(f"{BASE}/extract", headers=H(token), params={"project_id": project_id}),
        "POST /extract",
    )
    spec = extract_resp["spec"]
    print(f"     Spec title: {spec['title']}")
    print(f"     Overridden input_data values:")
    # Compare with template defaults to show what AI changed
    import copy
    template_path = "templates/specs/vodootvedenie_ochistnye_sooruzheniya.json"
    with open(template_path, encoding="utf-8") as tf:
        tpl_defaults = {item["id"]: item["value"] for item in json.load(tf)["input_data"]}
    for item in spec["input_data"]:
        tpl_val = tpl_defaults.get(item["id"])
        if tpl_val != item["value"]:
            print(f"       CHANGED  {item['id']}: {tpl_val} -> {item['value']}")
        else:
            print(f"       same     {item['id']}: {item['value']}")

    # 4. POST /compute
    compute_resp = check(
        CLIENT.post(f"{BASE}/compute", headers=H(token), params={"project_id": project_id}),
        "POST /compute",
    )
    results = compute_resp["results"]

    REFERENCE = [
        ("Q_sr_chas", 1666.67, 0.01),
        ("Q_sr_sek", 0.463, 0.001),
        ("K_max", 1.5093, 0.0005),
        ("q_max_sek", 0.699, 0.001),
        ("v_r_ms", 0.741, 0.001),
        ("a_smesh", 0.694, 0.002),
        ("n_razb", 53.462, 0.2),
        ("E_b", 87.53, 0.05),
        ("E_L", 84.04, 0.05),
        ("E_O2", 88.59, 0.05),
        ("n_resh", 160, 0),
        ("L_pes", 18.558, 0.02),
        ("n_per", 10, 0),
        ("W_aer", 10753.33, 10),
        ("S_vtor", 2224.139, 3),
        ("V_hl", 1257.75, 1.5),
        ("T_hl_min", 30, 0),
    ]

    print("\n  Reference check (key results):")
    failures = []
    for step_id, ref, tol in REFERENCE:
        got = results.get(step_id)
        if got is None:
            failures.append((step_id, ref, "MISSING"))
            print(f"    MISS  {step_id:>16}: ref={ref}")
        elif abs(got - ref) > tol:
            failures.append((step_id, ref, got))
            print(f"    FAIL  {step_id:>16}: ref={ref}  got={got:.4f}")
        else:
            print(f"    ok    {step_id:>16}: ref={ref}  got={got:.4f}")

    # 5. POST /generate
    generate_resp = check(
        CLIENT.post(
            f"{BASE}/generate",
            headers=H(token),
            params={"project_id": project_id},
            json={
                "university": "Уфимский государственный нефтяной технический университет",
                "student_name": "Тестов Тест Тестович",
                "group": "БТП-21-01",
                "supervisor": "Иванов И.И.",
                "city_year": "Уфа, 2024",
            },
        ),
        "POST /generate",
    )
    docx_url = generate_resp.get("docx_url", "")
    pdf_url = generate_resp.get("pdf_url", "")
    warning = generate_resp.get("warning")
    if warning:
        print(f"     Warning: {warning}")

    # Download docx
    if docx_url:
        r = CLIENT.get(docx_url)
        docx_path = os.path.join(OUT_DIR, "report.docx")
        with open(docx_path, "wb") as f:
            f.write(r.content)
        print(f"     Saved docx -> {os.path.abspath(docx_path)} ({len(r.content):,} bytes)")

    # Download pdf
    if pdf_url:
        r = CLIENT.get(pdf_url)
        pdf_path = os.path.join(OUT_DIR, "report.pdf")
        with open(pdf_path, "wb") as f:
            f.write(r.content)
        print(f"     Saved pdf  -> {os.path.abspath(pdf_path)} ({len(r.content):,} bytes)")

    print()
    if failures:
        print(f"RESULT: {len(failures)} reference mismatches:")
        for step_id, ref, got in failures:
            print(f"  {step_id}: ref={ref}  got={got}")
        sys.exit(1)
    else:
        print(f"RESULT: all {len(REFERENCE)} reference checks passed — flow OK")


if __name__ == "__main__":
    main()
