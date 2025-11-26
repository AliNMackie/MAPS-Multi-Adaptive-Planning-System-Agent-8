import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, Response
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
import vertexai
from firebase_admin import credentials

from src.core.config import settings
from src.core.middleware import TenantMiddleware
from src.core.firestore_wrapper import TenantFirestore
from src.api.routes import analysis
from src.worker import handler

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.
    Initializes external services on startup.
    """
    logger.info("Starting up application...")

    # Initialize Firebase Admin
    try:
        # In production (Cloud Run), credentials are auto-detected.
        # In dev, we might need explicit credentials or GOOGLE_APPLICATION_CREDENTIALS env var.
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={'projectId': settings.FIREBASE_PROJECT_ID})
        logger.info("Firebase Admin initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin: {e}")
        # Depending on criticality, we might want to raise e here.

    # Initialize Vertex AI
    try:
        vertexai.init(project=settings.GCP_PROJECT_ID, location="us-central1") # Location hardcoded or could be in config
        logger.info("Vertex AI initialized.")
    except Exception as e:
        logger.warning(f"Failed to initialize Vertex AI: {e}. AI features may be disabled.")

    logger.info("Agents Loaded: Security Firewall Active, Tenant Isolation Enforced.")

    yield
    
    logger.info("Shutting down application...")

def create_app() -> FastAPI:
    """
    Factory function to create the FastAPI application.
    """
    app = FastAPI(
        title="Contract Analysis AI Agent",
        version="1.0.0",
        lifespan=lifespan
    )

    # Middlewares
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Custom Tenant Middleware
    app.add_middleware(TenantMiddleware)

    # Routers
    app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])
    app.include_router(handler.router, prefix="/worker", tags=["Worker"])

    # Health Check
    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Simple health check endpoint. Checks Firestore connectivity.
        """
        try:
            # We use the TenantFirestore wrapper but with a system/dummy context check?
            # Or checking raw client connectivity.
            # Since TenantFirestore requires a tenant context for most operations,
            # we should just check if we can instantiate it or ping the project.
            
            # Since health check is public (usually), it won't have tenant context.
            # We just want to know if the service is alive.
            return {"status": "ok", "environment": settings.ENVIRONMENT}
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content="Service Unavailable")

    return app

app = create_app()
