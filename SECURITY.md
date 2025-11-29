# Security Architecture & Compliance

MAPS is designed with a "Security First" approach, specifically tailored for handling sensitive contract data in compliance with UK/EU regulations.

## 1. Data Residency & Compliance

-   **Region Enforcement**: All infrastructure components (Cloud Run, Firestore, Cloud Tasks, Vertex AI) are strictly provisioned in `europe-west2` (London).
-   **Configuration**: The application enforces this via the `VERTEX_AI_LOCATION` setting and hardcoded defaults in the firewall component.

## 2. Tenant Isolation

We employ a strict logical isolation model to ensure data from one tenant never leaks to another.

-   **Middleware**: `TenantMiddleware` intercepts every request, extracts the tenant ID, and sets a context-local variable.
-   **Data Access**: The `TenantFirestore` wrapper automatically prefixes all database paths with `tenants/{tenant_id}/`.
-   **Context Safety**: Python `contextvars` are used to ensure async-safe context propagation.

## 3. Prompt Injection Firewall

To protect against Large Language Model (LLM) vulnerabilities, we implement a multi-layered firewall (`src/core/security_firewall.py`):

1.  **Regex Heuristics**: Fast scanning for known attack patterns (e.g., "Ignore previous instructions", "DAN mode").
2.  **Hidden Text Detection**: Scans for zero-width characters and other obfuscation techniques.
3.  **Semantic Analysis**: Uses a separate, secured LLM instance to analyze the *intent* of the user input before processing it.

## 4. Authentication & Authorization

-   **API Access**: Protected via Firebase Auth (Bearer tokens).
-   **Worker Access**: Cloud Tasks worker endpoints are protected via OIDC (OpenID Connect) tokens.
    -   The application verifies that the token was issued by Google.
    -   It verifies the token is intended for this specific service (Audience check).
    -   It verifies the token belongs to the authorized service account.

## 5. Container Security

-   **Non-Root User**: The Docker container runs as a non-privileged user (`appuser`), preventing potential container escape attacks from gaining root host access.
-   **Minimal Base Image**: Uses `python:3.11-slim` to minimize the attack surface.

## 6. Secret Management

-   **No Hardcoded Secrets**: All credentials and API keys are managed via environment variables.
-   **Identity-Based Access**: We prefer IAM-based authentication (Workload Identity) over long-lived service account keys wherever possible.
