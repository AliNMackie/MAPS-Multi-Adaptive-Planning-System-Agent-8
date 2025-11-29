# MAPS - Multi-Adaptive Planning System

**A production-ready, multi-tenant AI contract analysis system built for Google Cloud Platform with enterprise-grade security and tenant isolation.**

## Overview

MAPS is a FastAPI-based microservice that provides intelligent contract analysis using Google's Vertex AI. The system features comprehensive security controls including tenant isolation, prompt injection detection, and OIDC-based authentication for worker processes.

### Key Features

- 🔒 **Multi-Tenant Architecture**: Complete data isolation between tenants using Firestore
- 🛡️ **Security Firewall**: AI-powered prompt injection and jailbreak detection
- ☁️ **Cloud-Native Design**: Built for Google Cloud Run with Cloud Tasks async processing
- 🌍 **EU Compliance**: Data residency controls using europe-west2 region
- 🔐 **Enterprise Security**: OIDC token verification, non-root containers, secure defaults
- 📊 **Production-Ready**: Health checks, structured logging, graceful error handling

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /api/v1/analyze
       ▼
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│  ┌──────────────────────────────────┐   │
│  │   Tenant Middleware              │   │
│  │   (Context Isolation)            │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │   Analysis Router                │   │
│  │   1. Create job in Firestore     │   │
│  │   2. Enqueue to Cloud Tasks      │   │
│  └──────────────────────────────────┘   │
└────────────┬────────────────────────────┘
             │
             ▼
      ┌─────────────┐
      │ Cloud Tasks │
      │   Queue     │
      └──────┬──────┘
             │ HTTP POST /worker/process (OIDC)
             ▼
      ┌─────────────────────────────────┐
      │   Worker Handler                │
      │   1. Verify OIDC token          │
      │   2. Security scan (Firewall)   │
      │   3. Run AI analysis            │
      │   4. Update Firestore           │
      └─────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- Google Cloud Platform account
- GCP Project with APIs enabled:
  - Firestore
  - Cloud Tasks
  - Vertex AI
  - Cloud Run (for deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/AliNMackie/MAPS-Multi-Adaptive-Planning-System-Agent-8.git
   cd MAPS-Multi-Adaptive-Planning-System-Agent-8
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your GCP project details
   ```

5. **Set up GCP authentication**
   ```bash
   gcloud auth application-default login
   # Or set GOOGLE_APPLICATION_CREDENTIALS to your service account key
   ```

6. **Run the application**
   ```bash
   uvicorn src.main:app --reload --port 8080
   ```

7. **Verify health**
   ```bash
   curl http://localhost:8080/health
   curl http://localhost:8080/readiness
   ```

## Environment Variables

All configuration is managed through environment variables. See `.env.example` for a complete template.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | `my-project-123` |
| `FIREBASE_PROJECT_ID` | Firebase Project ID (usually same as GCP) | `my-project-123` |
| `TASK_QUEUE_PATH` | Full path to Cloud Task Queue | `projects/my-project/locations/europe-west2/queues/default` |
| `ENVIRONMENT` | Deployment environment | `dev` or `prod` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port (set by Cloud Run) | `8080` |
| `VERTEX_AI_LOCATION` | Vertex AI region | `europe-west2` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |
| `SERVICE_ACCOUNT_EMAIL` | Cloud Tasks service account | Required for production |
| `SERVICE_URL` | Service URL for callbacks | `http://localhost:8080` |

## API Documentation

### Analyze Contract

**Endpoint**: `POST /api/v1/analyze`

**Headers**:
- `Authorization: Bearer <firebase-id-token>`
- `Content-Type: application/json`

**Request Body**:
```json
{
  "contract_text": "This agreement is made between..."
}
```

**Response** (202 Accepted):
```json
{
  "job_id": "uuid-v4",
  "status": "queued"
}
```

### Health Check

**Endpoint**: `GET /health`

**Response** (200 OK):
```json
{
  "status": "ok",
  "environment": "dev"
}
```

### Readiness Check

**Endpoint**: `GET /readiness`

**Response** (200 OK if all services available):
```json
{
  "firestore": true,
  "vertex_ai": true
}
```

## Deployment to Google Cloud Platform

### Using Cloud Run (Recommended)

1. **Build and push Docker image**
   ```bash
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/maps
   ```

2. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy maps \
     --image gcr.io/YOUR_PROJECT_ID/maps \
     --platform managed \
     --region europe-west2 \
     --allow-unauthenticated \
     --set-env-vars GCP_PROJECT_ID=YOUR_PROJECT_ID,FIREBASE_PROJECT_ID=YOUR_PROJECT_ID \
     --set-env-vars TASK_QUEUE_PATH=projects/YOUR_PROJECT_ID/locations/europe-west2/queues/default \
     --set-env-vars ENVIRONMENT=prod \
     --set-env-vars VERTEX_AI_LOCATION=europe-west2
   ```

3. **Configure Cloud Tasks**
   ```bash
   gcloud tasks queues create default \
     --location=europe-west2
   ```

For detailed deployment instructions including IAM permissions, Firestore setup, and CI/CD configuration, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Security Features

### Tenant Isolation

- Every request is scoped to a tenant ID extracted from Firebase Auth tokens
- Firestore queries automatically prefixed with tenant path
- Context variables prevent cross-tenant data leakage

### Prompt Injection Firewall

The security firewall inspects all user input for:
- Prompt injection attempts (e.g., "ignore previous instructions")
- Jailbreak patterns (e.g., "DAN mode")
- Hidden text (zero-width characters)
- Malicious intent using AI-based semantic analysis

### OIDC Authentication

Worker endpoints verify OIDC tokens to ensure requests originate from authorized Cloud Tasks service accounts.

### Data Residency

All AI processing uses `europe-west2` (London) to comply with UK/EU data residency requirements.

For complete security documentation, see [SECURITY.md](SECURITY.md).

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_isolation.py

# Run with coverage
pytest --cov=src tests/
```

## Project Structure

```
maps/
├── src/
│   ├── main.py                    # FastAPI application factory
│   ├── core/
│   │   ├── config.py              # Pydantic settings
│   │   ├── firestore_wrapper.py   # Tenant-scoped Firestore client
│   │   ├── middleware.py          # Tenant context middleware
│   │   ├── queue.py               # Cloud Tasks wrapper
│   │   ├── security.py            # Authentication & tenant context
│   │   └── security_firewall.py   # Prompt injection detection
│   ├── api/
│   │   └── routes/
│   │       └── analysis.py        # Contract analysis endpoint
│   ├── worker/
│   │   └── handler.py             # Cloud Tasks worker
│   └── agent/
│       └── main.py                # AI analysis logic
├── tests/
│   ├── test_isolation.py
│   └── test_api_integration.py
├── Dockerfile                     # Production container
├── requirements.txt
├── .env.example                   # Environment template
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Copyright © 2025. All rights reserved.

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Built with ❤️ for enterprise-grade AI contract analysis**
