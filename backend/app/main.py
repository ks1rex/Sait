"""
FastAPI application — entry point.
All business logic lives in dedicated modules (pdf_extract, calc_engine, etc.).
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Dict, List, Optional

import fitz
from dotenv import load_dotenv
from docx import Document
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as jose_jwt
from pydantic import BaseModel, Field, ValidationError

from .ai_provider import AI_PROVIDER, extract_calculation_spec, generate_conclusion
from .calc_engine import CalcError, run_calculation
from .docx_generator import generate_docx
from .gost_styles import apply_gost_styles, remove_toc_section
from .pdf_extract import extract_text_and_tables
from .schemas import CalculationSpec
from .supabase_client import get_supabase

load_dotenv()

app = FastAPI(
    title="GOST Calculator API",
    description="Backend для генерации расчётных работ по ГОСТ",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_bearer = HTTPBearer()

_PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream", "binary/octet-stream"}
_TEXT_CONTENT_TYPES = {"text/plain", "text/csv"}

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_MANIFEST_PATH = _TEMPLATES_DIR / "manifest.json"
_VALID_GENERATION_MODES = {"universal", "fixed_template", "custom_template"}


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    try:
        payload = jose_jwt.decode(
            credentials.credentials,
            os.environ["SUPABASE_JWT_SECRET"],
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {"user_id": payload["sub"], "email": payload.get("email", "")}
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": f"Недействительный токен: {exc}"},
        )


CurrentUser = Annotated[dict, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str


class UploadedFile(BaseModel):
    file_type: str       # task | methodology | variant_data
    storage_path: str
    original_name: str


class UploadResponse(BaseModel):
    project_id: str
    files: List[UploadedFile]
    task_text_length: int


class ExtractResponse(BaseModel):
    project_id: str
    spec: CalculationSpec


class ComputeRequest(BaseModel):
    project_id: str


class ComputeResponse(BaseModel):
    project_id: str
    results: Dict[str, float]


class GenerateMeta(BaseModel):
    university: str = ""
    student_name: str = ""
    group: str = ""
    supervisor: str = ""
    city_year: str = ""


class GenerateRequest(BaseModel):
    project_id: str
    meta: GenerateMeta = Field(default_factory=GenerateMeta)


class GenerateResponse(BaseModel):
    project_id: str
    docx_url: str
    pdf_url: Optional[str] = None
    warning: Optional[str] = None


class TemplateInfo(BaseModel):
    id: str
    title: str
    discipline: str = ""
    work_type: str = ""
    description: str = ""
    spec_file: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_project(project_id: str, user_id: str) -> dict:
    """Loads a project row and verifies ownership. Raises 404 if not found."""
    db = get_supabase()
    result = (
        db.table("projects")
        .select("*")
        .eq("id", project_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Проект не найден"},
        )
    return result.data[0]


def _validate_pdf_bytes(pdf_bytes: bytes, label: str) -> None:
    """Raises HTTP 400 if bytes are not a readable PDF with at least one page."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = doc.page_count
        doc.close()
    except fitz.FileDataError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"{label}: невалидный или повреждённый PDF-файл"},
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"{label}: не удалось открыть файл как PDF"},
        )
    if page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"{label}: PDF не содержит страниц"},
        )


def _bytes_to_text(file_bytes: bytes, filename: str, content_type: str | None) -> str:
    """Convert uploaded file bytes to plain text (handles PDF and TXT)."""
    is_text = (
        content_type in _TEXT_CONTENT_TYPES
        or (filename or "").lower().endswith(".txt")
    )
    if is_text:
        return file_bytes.decode("utf-8", errors="replace")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return extract_text_and_tables(tmp_path)
    finally:
        os.unlink(tmp_path)


def _download_and_extract(storage_path: str) -> str:
    """Download a file from 'uploads' bucket and extract its text."""
    db = get_supabase()
    try:
        file_bytes: bytes = db.storage.from_("uploads").download(storage_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Не удалось скачать файл {storage_path}: {exc}"},
        )
    ext = storage_path.rsplit(".", 1)[-1].lower() if "." in storage_path else ""
    content_type = "text/plain" if ext == "txt" else "application/pdf"
    return _bytes_to_text(file_bytes, storage_path, content_type)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=app.version)


@app.get("/templates", response_model=List[TemplateInfo], tags=["templates"])
async def list_templates(user: CurrentUser) -> List[TemplateInfo]:
    """
    Возвращает список доступных фиксированных шаблонов расчёта из
    templates/manifest.json. Используется в режиме fixed_template.
    """
    if not _MANIFEST_PATH.exists():
        return []
    try:
        data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        return [TemplateInfo(**item) for item in data]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Не удалось прочитать список шаблонов: {exc}"},
        )


@app.post("/upload", response_model=UploadResponse, tags=["projects"])
async def upload_pdf(
    task: Annotated[UploadFile, File(description="PDF: задание (обязательно)")],
    methodology: Annotated[
        Optional[UploadFile], File(description="PDF: методичка (опционально)")
    ] = None,
    variant_data: Annotated[
        Optional[UploadFile], File(description="PDF или TXT: исходные данные по варианту (опционально)")
    ] = None,
    generation_mode: Annotated[
        str,
        Form(description="Режим генерации: universal | fixed_template | custom_template"),
    ] = "universal",
    template_id: Annotated[
        Optional[str],
        Form(description="ID шаблона из GET /templates (только для fixed_template)"),
    ] = None,
    user: CurrentUser = None,
) -> UploadResponse:
    """
    Принимает до трёх файлов: задание (обязательно), методичка и
    исходные данные по варианту (оба опциональны).
    Сохраняет каждый в Storage, создаёт записи в project_files.

    generation_mode=fixed_template + template_id указывает, что для этого
    проекта будет использоваться готовый зашитый шаблон расчёта.
    """
    if generation_mode not in _VALID_GENERATION_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": (
                    f"Недопустимый generation_mode '{generation_mode}'. "
                    f"Допустимые значения: {sorted(_VALID_GENERATION_MODES)}"
                )
            },
        )

    if generation_mode == "fixed_template" and not template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Для режима fixed_template необходимо указать template_id"},
        )
    if task.content_type not in _PDF_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Поле 'task' должно содержать PDF-файл"},
        )

    task_bytes = await task.read()
    if not task_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Файл задания пустой"},
        )

    _validate_pdf_bytes(task_bytes, "Задание")

    task_text = _bytes_to_text(task_bytes, task.filename or "", task.content_type)
    if not task_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": (
                    "Не удалось извлечь текст из PDF задания. "
                    "Возможно, файл отсканирован без распознавания (OCR)."
                )
            },
        )

    # Read optional files
    methodology_bytes: bytes | None = None
    if methodology and methodology.filename:
        methodology_bytes = await methodology.read()
        if methodology_bytes:
            _validate_pdf_bytes(methodology_bytes, "Методичка")
        else:
            methodology_bytes = None

    variant_data_bytes: bytes | None = None
    if variant_data and variant_data.filename:
        variant_data_bytes = await variant_data.read()
        if not variant_data_bytes:
            variant_data_bytes = None

    # Generate project ID and upload files to Storage
    project_id = str(uuid.uuid4())
    user_id: str = user["user_id"]
    db = get_supabase()

    uploaded: list[UploadedFile] = []
    storage_paths: list[str] = []  # for rollback

    def _upload_one(file_bytes: bytes, file_type: str, suffix: str, content_type: str, original_name: str) -> UploadedFile:
        path = f"{user_id}/{project_id}/{file_type}{suffix}"
        try:
            db.storage.from_("uploads").upload(
                path=path,
                file=file_bytes,
                file_options={"content-type": content_type},
            )
        except Exception as exc:
            # rollback already-uploaded files
            if storage_paths:
                try:
                    db.storage.from_("uploads").remove(storage_paths)
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": f"Ошибка загрузки файла {file_type} в хранилище: {exc}"},
            )
        storage_paths.append(path)
        return UploadedFile(file_type=file_type, storage_path=path, original_name=original_name)

    uploaded.append(_upload_one(task_bytes, "task", ".pdf", "application/pdf", task.filename or "task.pdf"))

    if methodology_bytes:
        uploaded.append(_upload_one(methodology_bytes, "methodology", ".pdf", "application/pdf", methodology.filename or "methodology.pdf"))  # type: ignore[union-attr]

    if variant_data_bytes:
        vd_filename = variant_data.filename or "variant_data"  # type: ignore[union-attr]
        is_txt = (variant_data.content_type in _TEXT_CONTENT_TYPES or vd_filename.lower().endswith(".txt"))  # type: ignore[union-attr]
        vd_suffix = ".txt" if is_txt else ".pdf"
        vd_ct = "text/plain" if is_txt else "application/pdf"
        uploaded.append(_upload_one(variant_data_bytes, "variant_data", vd_suffix, vd_ct, vd_filename))

    # Create project record
    title = os.path.splitext(task.filename or "Без названия")[0]
    project_row: dict = {
        "id": project_id,
        "user_id": user_id,
        "title": title,
        "status": "uploaded",
        "generation_mode": generation_mode,
    }
    if template_id:
        project_row["template_id"] = template_id
    try:
        db.table("projects").insert(project_row).execute()
    except Exception as exc:
        try:
            db.storage.from_("uploads").remove(storage_paths)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Ошибка создания проекта в БД: {exc}"},
        )

    # Create project_files records
    try:
        db.table("project_files").insert(
            [
                {
                    "project_id": project_id,
                    "file_type": f.file_type,
                    "storage_path": f.storage_path,
                    "original_name": f.original_name,
                }
                for f in uploaded
            ]
        ).execute()
    except Exception as exc:
        # project + files in storage already created — surface the error but don't rollback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Ошибка записи метаданных файлов: {exc}"},
        )

    return UploadResponse(
        project_id=project_id,
        files=uploaded,
        task_text_length=len(task_text),
    )


@app.post("/extract", response_model=ExtractResponse, tags=["projects"])
async def extract_spec(
    project_id: Annotated[str, Query(description="ID проекта, полученный из /upload")],
    user: CurrentUser,
) -> ExtractResponse:
    """
    Строит CalculationSpec для проекта в зависимости от generation_mode:
    - universal: AI извлекает структуру из загруженных PDF (текущая логика).
    - fixed_template / custom_template: заглушка, будет реализована в Блоке 3-6.
    """
    db = get_supabase()
    user_id: str = user["user_id"]

    # 1. Verify project ownership and load project row (contains generation_mode)
    project = _require_project(project_id, user_id)
    generation_mode: str = project.get("generation_mode", "universal")

    # ── Режимы, реализованные позже ─────────────────────────────────────────
    if generation_mode in ("fixed_template", "custom_template"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "status": "not_implemented_yet",
                "generation_mode": generation_mode,
                "message": (
                    f"Режим '{generation_mode}' будет реализован в следующих блоках. "
                    "Используйте generation_mode='universal' для текущей функциональности."
                ),
            },
        )

    # 2. Load file records for this project
    files_result = (
        db.table("project_files")
        .select("file_type, storage_path")
        .eq("project_id", project_id)
        .execute()
    )
    if not files_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "К проекту не привязано ни одного файла"},
        )

    files_by_type: dict[str, str] = {
        row["file_type"]: row["storage_path"] for row in files_result.data
    }

    if "task" not in files_by_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Файл задания (task) не найден в проекте"},
        )

    # 3. Download and extract text from each file
    task_text = _download_and_extract(files_by_type["task"])
    if not task_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Не удалось извлечь текст из файла задания"},
        )

    methodology_text: str | None = None
    if "methodology" in files_by_type:
        methodology_text = _download_and_extract(files_by_type["methodology"]) or None

    extra_inputs_text: str | None = None
    if "variant_data" in files_by_type:
        extra_inputs_text = _download_and_extract(files_by_type["variant_data"]) or None

    # 4. Call AI (primary model)
    try:
        ai_result = extract_calculation_spec(
            task_text=task_text,
            methodology_text=methodology_text,
            extra_inputs_text=extra_inputs_text,
            use_fallback_model=False,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": f"AI вернул некорректный JSON: {exc}"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": f"Ошибка при обращении к AI: {exc}"},
        )

    total_input_tokens = ai_result.input_tokens
    total_output_tokens = ai_result.output_tokens
    model_used = ai_result.model

    # 5. Validate with Pydantic; retry on fallback model if validation fails
    try:
        spec = CalculationSpec.model_validate(ai_result.spec_dict)
    except ValidationError:
        try:
            fallback = extract_calculation_spec(
                task_text=task_text,
                methodology_text=methodology_text,
                extra_inputs_text=extra_inputs_text,
                use_fallback_model=True,
            )
            total_input_tokens += fallback.input_tokens
            total_output_tokens += fallback.output_tokens
            model_used = fallback.model
            spec = CalculationSpec.model_validate(fallback.spec_dict)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": (
                        "Модель вернула некорректную структуру спецификации. "
                        "Попробуйте ещё раз или загрузите другой PDF."
                    ),
                    "validation_errors": exc.errors(),
                },
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": f"Fallback-модель вернула некорректный JSON: {exc}"},
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": f"Ошибка при обращении к fallback-модели: {exc}"},
            )

    # 6. Upsert spec into calculation_specs
    try:
        db.table("calculation_specs").upsert(
            {"project_id": project_id, "spec_json": spec.model_dump()},
            on_conflict="project_id",
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Ошибка сохранения спецификации: {exc}"},
        )

    # 7. Update project status
    db.table("projects").update({"status": "extracted"}).eq("id", project_id).execute()

    # 8. Log token usage (non-fatal)
    try:
        db.table("ai_usage").insert(
            {
                "user_id": user_id,
                "project_id": project_id,
                "provider": AI_PROVIDER,
                "model": model_used,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }
        ).execute()
    except Exception:
        pass

    return ExtractResponse(project_id=project_id, spec=spec)


@app.get("/spec/{project_id}", response_model=CalculationSpec, tags=["projects"])
async def get_spec(project_id: str, user: CurrentUser) -> CalculationSpec:
    """
    Возвращает сохранённую спецификацию расчёта для проекта.
    Используется фронтендом для отображения экрана проверки/редактирования.
    """
    _require_project(project_id, user["user_id"])

    db = get_supabase()
    result = (
        db.table("calculation_specs")
        .select("spec_json")
        .eq("project_id", project_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Спецификация ещё не создана. Сначала выполните /extract."},
        )
    return CalculationSpec.model_validate(result.data[0]["spec_json"])


@app.put("/spec/{project_id}", response_model=CalculationSpec, tags=["projects"])
async def update_spec(project_id: str, spec: CalculationSpec, user: CurrentUser) -> CalculationSpec:
    """
    Сохраняет отредактированную пользователем спецификацию.
    Экран проверки/редактирования — обязательный шаг перед /compute.
    """
    _require_project(project_id, user["user_id"])

    db = get_supabase()
    db.table("calculation_specs").update(
        {"spec_json": spec.model_dump()}
    ).eq("project_id", project_id).execute()

    return spec


@app.post("/compute", response_model=ComputeResponse, tags=["projects"])
async def compute(
    project_id: Annotated[str, Query(description="ID проекта")],
    user: CurrentUser,
) -> ComputeResponse:
    """
    Запускает расчётный движок по текущей (возможно, отредактированной)
    спецификации. Сохраняет step.value и conclusion_text обратно в БД.
    Не обращается к AI для расчёта — только для генерации заключения.
    """
    db = get_supabase()
    user_id: str = user["user_id"]

    # 1. Verify ownership
    _require_project(project_id, user_id)

    # 2. Load current spec (includes any user edits from PUT /spec)
    result = (
        db.table("calculation_specs")
        .select("spec_json")
        .eq("project_id", project_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Спецификация не найдена. Сначала выполните /extract."},
        )
    spec = CalculationSpec.model_validate(result.data[0]["spec_json"])

    # 3. Run calculation engine (mutates spec.sections[*].steps[*].value in place)
    try:
        results = run_calculation(spec)
    except CalcError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": str(exc), "step_id": exc.step_id},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Ошибка расчёта: {exc}"},
        )

    # 4. Generate conclusion via AI (non-fatal — report succeeds without it)
    try:
        spec.conclusion_text = generate_conclusion(spec.model_dump(), results)
    except Exception:
        spec.conclusion_text = None

    # 5. Persist updated spec (with computed values and conclusion)
    db.table("calculation_specs").update(
        {"spec_json": spec.model_dump()}
    ).eq("project_id", project_id).execute()

    # 6. Update project status
    db.table("projects").update({"status": "computed"}).eq("id", project_id).execute()

    return ComputeResponse(project_id=project_id, results=results)


_SOFFICE_TIMEOUT = 90  # seconds
# Resolves soffice executable: LIBREOFFICE_PATH env var → system PATH fallback.
# Windows example: C:\Program Files\LibreOffice\program\soffice.exe
# Linux/Docker:    soffice  (installed via apt, already on PATH)
_SOFFICE_BIN = os.getenv("LIBREOFFICE_PATH", "soffice")


@app.post("/generate", response_model=GenerateResponse, tags=["projects"])
async def generate(
    project_id: Annotated[str, Query(description="ID проекта")],
    user: CurrentUser,
    meta: Annotated[GenerateMeta, Body()] = GenerateMeta(),
) -> GenerateResponse:
    """
    Генерирует .docx через docx_generator и конвертирует в .pdf через
    LibreOffice headless. Загружает оба файла в bucket «outputs».
    Если LibreOffice недоступен — возвращает только docx с предупреждением
    в поле warning.
    """
    db = get_supabase()
    user_id: str = user["user_id"]

    # 1. Verify ownership and check status
    project = _require_project(project_id, user_id)
    if project["status"] not in ("computed", "done"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": (
                    "Расчёт ещё не выполнен. "
                    "Сначала выполните /compute."
                )
            },
        )

    # 2. Load computed spec
    result = (
        db.table("calculation_specs")
        .select("spec_json")
        .eq("project_id", project_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Спецификация не найдена."},
        )
    spec = CalculationSpec.model_validate(result.data[0]["spec_json"])

    # 3. Guard: all steps must have computed values
    uncomputed = [
        step.id
        for section in spec.sections
        for step in section.steps
        if step.value is None
    ]
    if uncomputed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Не все шаги вычислены. Выполните /compute заново.",
                "uncomputed_steps": uncomputed,
            },
        )

    storage_prefix = f"{user_id}/{project_id}"
    docx_storage_path = f"{storage_prefix}/report.docx"
    pdf_storage_path: Optional[str] = None
    pdf_warning: Optional[str] = None

    with tempfile.TemporaryDirectory() as tmp_dir:
        docx_path = os.path.join(tmp_dir, "report.docx")

        # 4. Generate .docx
        try:
            generate_docx(spec, meta.model_dump(), docx_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": f"Ошибка генерации docx: {exc}"},
            )

        # 5. Convert to .pdf via LibreOffice headless (optional)
        pdf_path = os.path.join(tmp_dir, "report.pdf")
        try:
            subprocess.run(
                [
                    _SOFFICE_BIN,
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", tmp_dir,
                    docx_path,
                ],
                check=True,
                capture_output=True,
                timeout=_SOFFICE_TIMEOUT,
            )
            if not os.path.exists(pdf_path):
                pdf_warning = "LibreOffice не создал PDF-файл (проверьте установку)."
                pdf_path = None
        except FileNotFoundError:
            pdf_warning = (
                "LibreOffice (soffice) не установлен на сервере. "
                "PDF-версия недоступна — скачайте .docx и конвертируйте самостоятельно."
            )
            pdf_path = None
        except subprocess.TimeoutExpired:
            pdf_warning = f"Конвертация в PDF превысила таймаут ({_SOFFICE_TIMEOUT} с)."
            pdf_path = None
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace")[:300] if exc.stderr else ""
            pdf_warning = f"Ошибка LibreOffice при конвертации: {stderr}"
            pdf_path = None

        # 6. Upload .docx to Storage (upsert — allow regeneration)
        with open(docx_path, "rb") as f:
            docx_bytes = f.read()
        try:
            db.storage.from_("outputs").upload(
                path=docx_storage_path,
                file=docx_bytes,
                file_options={
                    "content-type": (
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                    "upsert": "true",
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": f"Ошибка загрузки docx в хранилище: {exc}"},
            )

        # 7. Upload .pdf to Storage (if conversion succeeded)
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            try:
                pdf_storage_path = f"{storage_prefix}/report.pdf"
                db.storage.from_("outputs").upload(
                    path=pdf_storage_path,
                    file=pdf_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )
            except Exception as exc:
                pdf_warning = (pdf_warning or "") + f" Ошибка загрузки PDF: {exc}"
                pdf_storage_path = None

    # 8. Create signed URLs (1 hour)
    _SIGNED_URL_TTL = 3600
    try:
        docx_signed = db.storage.from_("outputs").create_signed_url(
            docx_storage_path, _SIGNED_URL_TTL
        )
        docx_url: str = docx_signed.get("signedURL", "")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Не удалось создать ссылку для скачивания docx: {exc}"},
        )

    pdf_url: Optional[str] = None
    if pdf_storage_path:
        try:
            pdf_signed = db.storage.from_("outputs").create_signed_url(
                pdf_storage_path, _SIGNED_URL_TTL
            )
            pdf_url = pdf_signed.get("signedURL")
        except Exception:
            pass  # signed URL failure is non-fatal for PDF

    # 9. Persist output paths and mark project done
    db.table("projects").update(
        {
            "output_docx_path": docx_storage_path,
            "output_pdf_path": pdf_storage_path,
            "status": "done",
        }
    ).eq("id", project_id).execute()

    return GenerateResponse(
        project_id=project_id,
        docx_url=docx_url,
        pdf_url=pdf_url,
        warning=pdf_warning,
    )


_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_DOCX_EXTENSIONS = {".docx"}


@app.post("/format-gost", tags=["tools"])
async def format_gost(
    file: Annotated[UploadFile, File(description=".docx файл для приведения к ГОСТ")],
    include_toc: Annotated[
        bool,
        Query(description="Сохранить раздел 'Содержание' (true) или удалить (false)"),
    ] = True,
    user: CurrentUser = None,
) -> Response:
    """
    Применяет ГОСТ-стили (поля, шрифты, межстрочный интервал, стили ячеек таблиц)
    к загруженному .docx файлу.

    Если include_toc=false — удаляет заголовок 'Содержание' и поле TOC из документа.
    Если include_toc=true и поля TOC нет — стили применяются без его добавления.

    Возвращает обработанный .docx файл для скачивания.
    Не требует project_id — работает как standalone утилита для любого документа.
    """
    filename = file.filename or "document.docx"
    ext = os.path.splitext(filename)[1].lower()

    is_docx = (
        ext in _DOCX_EXTENSIONS
        or file.content_type == _DOCX_CONTENT_TYPE
    )
    if not is_docx:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Поддерживаются только файлы .docx"},
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Загруженный файл пустой"},
        )

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Не удалось открыть файл как .docx: {exc}"},
        )

    try:
        apply_gost_styles(doc)
        if not include_toc:
            remove_toc_section(doc)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Ошибка применения стилей: {exc}"},
        )

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    safe_name = os.path.splitext(filename)[0] + "_gost.docx"
    return Response(
        content=buf.read(),
        media_type=_DOCX_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
