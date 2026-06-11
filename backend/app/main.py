"""
FastAPI application — entry point.
All business logic lives in dedicated modules (pdf_extract, calc_engine, etc.).
"""
from __future__ import annotations

import os
from typing import Annotated, Dict

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .schemas import CalculationSpec

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


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    """
    Validates Supabase JWT and returns the decoded payload.
    TODO: implement actual JWT verification.
    """
    # TODO: verify credentials.credentials against SUPABASE_JWT_SECRET
    # from jose import jwt as jose_jwt
    # payload = jose_jwt.decode(
    #     credentials.credentials,
    #     os.environ["SUPABASE_JWT_SECRET"],
    #     algorithms=["HS256"],
    #     audience="authenticated",
    # )
    # return {"user_id": payload["sub"], "email": payload.get("email")}
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="JWT verification not implemented yet",
    )


CurrentUser = Annotated[dict, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str


class UploadResponse(BaseModel):
    project_id: str
    storage_path: str
    filename: str
    text_length: int


class ExtractRequest(BaseModel):
    project_id: str


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
    pdf_url: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=app.version)


@app.post("/upload", response_model=UploadResponse, tags=["projects"])
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF файл задания")],
    user: CurrentUser,
) -> UploadResponse:
    """
    Принимает PDF, извлекает текст (pdf_extract.py), сохраняет в
    Supabase Storage bucket «uploads», создаёт запись в таблице projects.
    """
    # TODO: validate file.content_type == "application/pdf"
    # TODO: write file to temp path (tempfile.NamedTemporaryFile)
    # TODO: from .pdf_extract import extract_text_from_pdf
    #       text = extract_text_from_pdf(tmp_path)
    # TODO: upload file bytes to Supabase Storage "uploads/{user_id}/{uuid}.pdf"
    # TODO: db = get_supabase()
    #       row = db.table("projects").insert({
    #           "user_id": user["user_id"],
    #           "storage_path": storage_path,
    #           "filename": file.filename,
    #           "extracted_text": text,
    #       }).execute()
    # TODO: return UploadResponse(project_id=row.data[0]["id"], ...)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@app.post("/extract", response_model=ExtractResponse, tags=["projects"])
async def extract_spec(body: ExtractRequest, user: CurrentUser) -> ExtractResponse:
    """
    Загружает extracted_text из БД, отправляет в DeepSeek (ai_provider.py),
    валидирует ответ по CalculationSpec, сохраняет в calculation_specs.
    Повторный вызов перезаписывает спецификацию — расчёт (/compute) не трогает.
    """
    # TODO: db = get_supabase()
    #       project = db.table("projects").select("*")
    #           .eq("id", body.project_id).eq("user_id", user["user_id"])
    #           .single().execute().data
    #       if not project: raise HTTPException(404)
    # TODO: from .ai_provider import extract_calculation_spec
    #       spec_dict = extract_calculation_spec(project["extracted_text"])
    # TODO: spec = CalculationSpec.model_validate(spec_dict)
    # TODO: db.table("calculation_specs").upsert({
    #           "project_id": body.project_id,
    #           "spec_json": spec.model_dump(),
    #       }).execute()
    # TODO: db.table("ai_usage").insert({
    #           "user_id": user["user_id"], "project_id": body.project_id,
    #           "endpoint": "extract",
    #       }).execute()
    # TODO: return ExtractResponse(project_id=body.project_id, spec=spec)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@app.get("/spec/{project_id}", response_model=CalculationSpec, tags=["projects"])
async def get_spec(project_id: str, user: CurrentUser) -> CalculationSpec:
    """
    Возвращает сохранённую спецификацию расчёта для проекта.
    Используется фронтендом для отображения экрана проверки/редактирования.
    """
    # TODO: db = get_supabase()
    #       row = db.table("calculation_specs")
    #           .select("spec_json, projects(user_id)")
    #           .eq("project_id", project_id).single().execute().data
    #       if not row: raise HTTPException(404)
    #       if row["projects"]["user_id"] != user["user_id"]: raise HTTPException(403)
    # TODO: return CalculationSpec.model_validate(row["spec_json"])
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@app.put("/spec/{project_id}", response_model=CalculationSpec, tags=["projects"])
async def update_spec(project_id: str, spec: CalculationSpec, user: CurrentUser) -> CalculationSpec:
    """
    Сохраняет отредактированную пользователем спецификацию.
    Экран проверки/редактирования — обязательный шаг перед /compute.
    """
    # TODO: проверить ownership (аналогично get_spec)
    # TODO: db.table("calculation_specs").update({"spec_json": spec.model_dump()})
    #           .eq("project_id", project_id).execute()
    # TODO: return spec
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@app.post("/compute", response_model=ComputeResponse, tags=["projects"])
async def compute(body: ComputeRequest, user: CurrentUser) -> ComputeResponse:
    """
    Запускает расчётный движок (calc_engine.py) по сохранённой спецификации.
    Не обращается к AI — использует уже проверенную пользователем спецификацию.
    """
    # TODO: загрузить спецификацию из БД + проверить ownership
    # TODO: from .calc_engine import run_calculation
    #       results = run_calculation(spec)  # мутирует step.value внутри spec
    # TODO: сохранить обновлённую spec (с заполненными step.value) обратно в БД
    # TODO: return ComputeResponse(project_id=body.project_id, results=results)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")


@app.post("/generate", response_model=GenerateResponse, tags=["projects"])
async def generate(body: GenerateRequest, user: CurrentUser) -> GenerateResponse:
    """
    Генерирует .docx (docx_generator.py) и конвертирует в .pdf
    (LibreOffice headless), загружает оба файла в Supabase Storage «outputs».
    """
    # TODO: загрузить спецификацию + проверить, что /compute был запущен
    #       (все step.value != None), проверить ownership
    # TODO: если spec.conclusion_text is None:
    #       from .ai_provider import generate_conclusion
    #       spec.conclusion_text = generate_conclusion(spec.model_dump(), results)
    # TODO: import tempfile, subprocess
    #       with tempfile.TemporaryDirectory() as tmp:
    #           docx_path = f"{tmp}/report.docx"
    #           from .docx_generator import generate_docx
    #           generate_docx(spec, body.meta.model_dump(), docx_path)
    #           subprocess.run(
    #               ["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, docx_path],
    #               check=True,
    #           )
    #           pdf_path = docx_path.replace(".docx", ".pdf")
    # TODO: загрузить оба файла в bucket "outputs" и вернуть signed URLs
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented")
