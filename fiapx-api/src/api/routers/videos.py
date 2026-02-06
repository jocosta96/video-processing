from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from src.api.dependencies import CurrentUser, DatabaseSession, verify_job_ownership
from src.api.schemas import JobListResponse, JobResponse, UploadResponse
from src.core.config import settings
from src.core.messaging import get_publisher
from src.models import Job, JobStatus
from src.services import StorageService

logger = structlog.get_logger()
router = APIRouter(prefix="/videos", tags=["Videos"])

SUPPORTED_FORMATS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload de video",
    description=f"""
Envia um video para processamento de extracao de frames.

**Formatos suportados:** `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`

**Tamanho maximo:** {settings.max_video_size_mb}MB

**Processo:**
1. Video e salvo no storage
2. Job e criado com status `QUEUED`
3. Worker processa o video em background
4. Frames sao extraidos (1 por segundo)
5. ZIP e criado e disponibilizado para download
    """,
)
async def upload_video(
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(..., description="Arquivo de video para processar"),
) -> UploadResponse:
    """
    Faz upload de um video para extracao de frames.

    Retorna o ID do job para acompanhar o processamento.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported format. Allowed: {SUPPORTED_FORMATS}")

    file_content = await file.read()
    file_size = len(file_content)

    if file_size > settings.max_video_size_bytes:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.max_video_size_mb}MB")

    job = Job(
        user_id=current_user.id,
        status=JobStatus.UPLOADED,
        video_path="",
        video_size_bytes=file_size,
        video_format=ext.lstrip("."),
        original_filename=file.filename,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.video_retention_days),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    video_key = f"videos/{current_user.id}/{job.id}/input{ext}"

    try:
        storage = StorageService()
        storage.upload_file(BytesIO(file_content), video_key, file.content_type)
    except Exception as e:
        logger.error("upload_failed", job_id=str(job.id), error=str(e))
        db.delete(job)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to upload file")

    job.video_path = video_key
    job.status = JobStatus.QUEUED
    db.commit()

    publisher = get_publisher()
    publisher.publish_video_job(str(job.id), str(current_user.id), video_key)

    logger.info("video_uploaded", job_id=str(job.id), user_id=str(current_user.id))

    return UploadResponse(job_id=job.id, status=job.status, message="Video queued for processing")


@router.get(
    "",
    response_model=JobListResponse,
    summary="Listar videos",
    description="Lista todos os videos/jobs do usuario autenticado com paginacao.",
)
async def list_videos(
    current_user: CurrentUser,
    db: DatabaseSession,
    skip: int = Query(0, ge=0, description="Itens para pular"),
    limit: int = Query(50, ge=1, le=100, description="Quantidade de itens"),
):
    """Lista videos do usuario com paginacao."""
    query = db.query(Job).filter(Job.user_id == current_user.id)
    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    return JobListResponse(jobs=[JobResponse.from_job(j) for j in jobs], total=total)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Detalhes do video",
    description="""
Retorna detalhes de um video/job especifico.

**Status possiveis:**
- `UPLOADED` - Video recebido
- `QUEUED` - Aguardando processamento
- `PROCESSING` - Extraindo frames
- `DONE` - Concluido, pronto para download
- `FAILED` - Erro no processamento
- `CANCELLED` - Cancelado pelo usuario
    """,
)
async def get_video(job_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Retorna detalhes de um video especifico."""
    job = verify_job_ownership(job_id, current_user, db)
    return JobResponse.from_job(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar video",
    description="Cancela um video que ainda nao foi processado (status UPLOADED ou QUEUED).",
)
async def cancel_video(job_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Cancela um job pendente."""
    job = verify_job_ownership(job_id, current_user, db)
    if job.status not in (JobStatus.UPLOADED, JobStatus.QUEUED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status: {job.status}")
    job.status = JobStatus.CANCELLED
    db.commit()
