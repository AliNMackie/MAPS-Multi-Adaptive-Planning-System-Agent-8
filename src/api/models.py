from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from src.core.middleware import get_current_user_context

class JobMetadata(BaseModel):
    client_id: str
    priority: int
    source_platform: Optional[Literal["google", "microsoft"]] = None

class JobCreate(BaseModel):
    name: str
    metadata: JobMetadata
    payload: Dict[str, Any]

    def __init__(self, **data):
        super().__init__(**data)
        # Automatically populate source_platform from Context if not provided
        if self.metadata.source_platform is None:
            ctx = get_current_user_context()
            if ctx:
                provider = ctx.auth_provider
                if provider == "google.com":
                    self.metadata.source_platform = "google"
                elif provider == "microsoft.com":
                    self.metadata.source_platform = "microsoft"
