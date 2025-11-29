import logging
from typing import List, Literal
from pydantic_settings import BaseSettings
from pydantic import Field

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # GCP Project Configuration
    GCP_PROJECT_ID: str = Field(..., description="Google Cloud Project ID")
    FIREBASE_PROJECT_ID: str = Field(..., description="Firebase Project ID (usually same as GCP)")
    
    # Cloud Tasks Configuration
    TASK_QUEUE_PATH: str = Field(..., description="Full path to Cloud Task Queue e.g. projects/.../queues/...")
    
    # Environment Configuration
    ENVIRONMENT: Literal["dev", "prod"] = Field("dev", description="Deployment environment")
    
    # Server Configuration
    PORT: int = Field(8080, description="Server port (required for Cloud Run/App Engine)")
    
    # Vertex AI Configuration
    VERTEX_AI_LOCATION: str = Field("europe-west2", description="Vertex AI location (must be europe-west2 for UK/EU compliance)")
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"], 
        description="List of allowed CORS origins"
    )
    
    # Optional: Service Account Email for OIDC
    SERVICE_ACCOUNT_EMAIL: str = Field(default="", description="Service Account Email for Cloud Tasks OIDC")
    
    # Optional: Service URL (for Cloud Tasks target)
    SERVICE_URL: str = Field(default="http://localhost:8080", description="URL of the deployed service")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"  # Allow extra fields in .env
    }

# Validate settings immediately on import
try:
    settings = Settings()
except Exception as e:
    logger.critical(f"Failed to load configuration: {e}")
    raise e
