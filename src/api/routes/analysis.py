from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from typing import Dict, Any
import uuid
import logging

from src.core.security import tenant_scoped, current_tenant
from src.core.firestore_wrapper import TenantFirestore
from src.core.queue import JobQueue

logger = logging.getLogger(__name__)

router = APIRouter()

class AnalyzeRequest(BaseModel):
    contract_text: str

class AnalyzeResponse(BaseModel):
    job_id: str
    status: str

# Dependency to get Firestore
def get_db():
    return TenantFirestore()

# Dependency to get Queue
def get_queue():
    return JobQueue()

@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
@tenant_scoped
async def analyze_contract(
    request: AnalyzeRequest,
    req: Request,  # Added Request object for @tenant_scoped decorator
    db: TenantFirestore = Depends(get_db),
    queue: JobQueue = Depends(get_queue)
):
    """
    Enqueues a contract analysis job.
    """
    tenant_id = current_tenant.get()
    if not tenant_id:
        raise HTTPException(status_code=500, detail="Tenant context missing")

    job_id = str(uuid.uuid4())
    
    # 1. Create Job in Firestore
    job_ref = db.collection(f"tenants/{tenant_id}/jobs").document(job_id)
    try:
        job_ref.set({
            "status": "QUEUED",
            "created_at": "NOW", # Real implementation uses firestore.SERVER_TIMESTAMP
            "input_text_length": len(request.contract_text),
            # Don't store full text if huge, or store in Cloud Storage. 
            # For this task, we store text in payload or separate field.
            # Storing text in Firestore is OK if < 1MB.
            "contract_text": request.contract_text 
        })
    except Exception as e:
        logger.error(f"Failed to create job in Firestore: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    # 2. Enqueue Job
    try:
        queue.enqueue_job(
            job_id=job_id, 
            tenant_id=tenant_id, 
            payload={"contract_text": request.contract_text}
        )
    except Exception as e:
        # If queue fails, we should probably mark job as FAILED or delete it.
        logger.error(f"Failed to enqueue job: {e}")
        job_ref.update({"status": "FAILED_QUEUE"})
        raise HTTPException(status_code=500, detail="Queue error")

    return AnalyzeResponse(job_id=job_id, status="queued")
