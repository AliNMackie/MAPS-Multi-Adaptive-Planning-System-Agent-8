from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Dict, Any
import logging
import os
from google.auth.transport import requests
from google.oauth2 import id_token

from src.core.firestore_wrapper import TenantFirestore
from src.core.security_firewall import PromptInjectionFirewall
from src.core.security import current_tenant

logger = logging.getLogger(__name__)

router = APIRouter()

class WorkerPayload(BaseModel):
    job_id: str
    tenant_id: str
    data: Dict[str, Any]

def verify_oidc_token(request: Request):
    """
    Verifies the OIDC token in the Authorization header.
    Ensures the request comes from Cloud Tasks (or a trusted source).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    
    # In a real environment, allow verification to be skipped for local testing if explicitly configured
    if os.getenv("SKIP_AUTH_CHECK", "false").lower() == "true":
        return

    try:
        # Verify the token
        # You normally specify the audience (your service URL)
        # For simplicity, we might verify signature without audience if we don't know it exactly dynamically,
        # but robust security requires audience check.
        # Assuming SERVICE_URL is set.
        # id_token.verify_oauth2_token(token, requests.Request(), audience=os.getenv("SERVICE_URL"))
        
        # We can also check email claim if we want to ensure it's OUR service account.
        id_info = id_token.verify_oauth2_token(token, requests.Request())
        
        # Optional: Check issuer or email
        # if id_info['email'] != expected_service_account: raise...
        
    except ValueError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

def run_analysis_logic(text: str) -> Dict[str, Any]:
    """
    Placeholder for the actual analysis logic.
    """
    return {
        "summary": "Contract analysis complete.",
        "risk_score": 0.5
    }

@router.post("/process", status_code=200)
async def process_job(
    payload: WorkerPayload,
    request: Request
):
    """
    Worker handler to process the job.
    """
    # 1. Verify Security (OIDC)
    verify_oidc_token(request)

    job_id = payload.job_id
    tenant_id = payload.tenant_id
    contract_text = payload.data.get("contract_text", "")

    logger.info(f"Processing job {job_id} for tenant {tenant_id}")

    # 2. Context Switching
    # We must manually set the context var because this request doesn't go through the user auth middleware
    token = current_tenant.set(tenant_id)
    
    try:
        db = TenantFirestore()
        
        # 3. Retrieve Job (Verify it exists and is QUEUED)
        # Note: We use the tenant-scoped DB wrapper which relies on current_tenant
        job_ref = db.collection(f"tenants/{tenant_id}/jobs").document(job_id)
        job_snap = job_ref.get()
        
        if not job_snap.exists:
            logger.error(f"Job {job_id} not found")
            return # Acknowledge task to remove from queue
            
        # 4. Security Scan
        firewall = PromptInjectionFirewall()
        scan_result = firewall.scan_prompt(contract_text)
        
        if not scan_result.is_safe:
            logger.warning(f"Security Scan Failed for job {job_id}: {scan_result.reasoning}")
            job_ref.update({
                "status": "FAILED",
                "error": f"Security Policy Violation: {scan_result.threat_type}",
                "security_scan": scan_result.model_dump()
            })
            return

        # 5. Run Analysis
        try:
            # Update status to PROCESSING
            job_ref.update({"status": "PROCESSING"})
            
            result = run_analysis_logic(contract_text)
            
            # 6. Complete
            job_ref.update({
                "status": "COMPLETED",
                "result": result,
                "security_scan": scan_result.model_dump()
            })
            
        except Exception as e:
            logger.error(f"Analysis failed for job {job_id}: {e}")
            job_ref.update({
                "status": "FAILED",
                "error": str(e)
            })
            # We might want to re-raise if we want Cloud Tasks to retry.
            # But if it's a logic error, retrying won't help.
            # Only re-raise transient errors.
            
    finally:
        # Reset context
        current_tenant.reset(token)
        
    return {"status": "ok"}
