import json
import logging
import os
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class JobQueue:
    def __init__(self, project_id: Optional[str] = None, location: str = "us-central1", queue_name: str = "default"):
        """
        Initializes the Cloud Tasks client.
        """
        # In a real environment, project_id and location would usually be pulled from environment variables.
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "test-project")
        self.location = location
        self.queue_name = queue_name
        
        try:
            self.client = tasks_v2.CloudTasksClient()
            self.parent = self.client.queue_path(self.project_id, self.location, self.queue_name)
        except Exception as e:
            logger.warning(f"Failed to initialize Cloud Tasks Client: {e}")
            self.client = None
            self.parent = None

    def enqueue_job(self, job_id: str, tenant_id: str, payload: Dict[str, Any], service_url: Optional[str] = None):
        """
        Enqueues a job to Cloud Tasks.
        Constructs a POST request to the worker endpoint.
        """
        if not self.client or not self.parent:
            logger.error("Cloud Tasks Client not initialized. Job not enqueued.")
            # In dev/test, we might just log this. In prod, this should raise an error.
            return

        if not service_url:
            # Fallback to an env var or a default service URL
            service_url = os.getenv("SERVICE_URL", "http://localhost:8080")
        
        # Construct the target URL
        url = f"{service_url.rstrip('/')}/worker/process"

        # Construct the payload
        task_payload = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "data": payload
        }
        
        # Convert payload to bytes
        json_payload = json.dumps(task_payload)
        payload_bytes = json_payload.encode("utf-8")

        # Construct the task
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": payload_bytes,
                # Add OIDC Token for authentication
                # This assumes the Cloud Tasks service account has permission to invoke the Cloud Run service.
                "oidc_token": {
                    "service_account_email": os.getenv("SERVICE_ACCOUNT_EMAIL", "default-sa@test.iam.gserviceaccount.com")
                }
            }
        }

        try:
            response = self.client.create_task(request={"parent": self.parent, "task": task})
            logger.info(f"Created task {response.name} for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            raise e
