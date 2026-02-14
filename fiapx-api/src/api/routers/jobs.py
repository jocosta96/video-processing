from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException

from src.api.dependencies import CurrentUser, DatabaseSession, verify_job_ownership
from src.api.schemas import DownloadResponse, JobStatusResponse
from src.core.config import settings
from src.models import JobStatus
from src.services import StorageService

logger = structlog.get_logger()
router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Status do job",
    description="""
Retorna o status atual de um job de processamento.

**Use para polling:** Consulte periodicamente ate o status ser `DONE` ou `FAILED`.

**Status possiveis:**
- `QUEUED` - Aguardando na fila
- `PROCESSING` - Processando video
- `DONE` - Pronto para download
- `FAILED` - Erro no processamento
- `CANCELLED` - Cancelado
    """,
)
async def get_job_status(job_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Retorna o status atual do job."""
    job = verify_job_ownership(job_id, current_user, db)

    messages = {
        JobStatus.QUEUED: "Waiting in queue",
        JobStatus.PROCESSING: "Processing video",
        JobStatus.DONE: "Ready for download",
        JobStatus.FAILED: job.error_message or "Processing failed",
        JobStatus.CANCELLED: "Job cancelled",
        JobStatus.EXPIRED: "Files expired",
    }

    return JobStatusResponse(
        id=job.id,
        status=job.status,
        progress="extracting_frames" if job.status == JobStatus.PROCESSING else None,
        message=messages.get(job.status),
    )


@router.get(
    "/{job_id}/download",
    response_model=DownloadResponse,
    summary="Download do ZIP",
    description=f"""
Gera uma URL assinada para download do arquivo ZIP com os frames extraidos.

**Requisitos:**
- Job deve estar com status `DONE`
- Arquivo nao pode ter expirado ({settings.video_retention_days} dias)

**URL retornada:**
- Valida por {settings.presigned_url_expiry_seconds // 60} minutos
- Pode ser usada diretamente no navegador

**Exemplo com curl:**
```bash
curl -L "URL_RETORNADA" -o frames.zip
```
    """,
)
async def get_download_url(job_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Gera URL de download para o ZIP com frames."""
    job = verify_job_ownership(job_id, current_user, db)

    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=400, detail=f"Job not complete. Status: {job.status}")

    if not job.zip_path:
        raise HTTPException(status_code=404, detail="ZIP file not found")

    if job.expires_at and job.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="File has expired")

    storage = StorageService()
    if not storage.file_exists(job.zip_path):
        raise HTTPException(status_code=404, detail="ZIP file not found in storage")

    filename = f"{job.original_filename.rsplit('.', 1)[0]}_frames.zip"
    expires_in = settings.presigned_url_expiry_seconds

    logger.info("download_url_generated", job_id=str(job.id), user_id=str(current_user.id))

    return DownloadResponse(
        download_url=storage.generate_presigned_url(job.zip_path, expires_in, filename),
        expires_in=expires_in,
        filename=filename,
    )
