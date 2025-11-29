# Deployment Guide for MAPS

This guide details the steps to deploy the Multi-Adaptive Planning System (MAPS) to Google Cloud Platform (GCP).

## Prerequisites

1.  **Google Cloud Project**: A GCP project with billing enabled.
2.  **Google Cloud SDK**: Installed and authenticated (`gcloud auth login`).
3.  **Docker**: Installed locally (optional, for local testing).

## 1. Environment Setup

Set your project variables:

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west2"  # Required for UK/EU compliance
export SERVICE_NAME="maps-service"
export QUEUE_NAME="default"
```

Enable required APIs:

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  cloudtasks.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com
```

## 2. Firestore Setup

1.  Go to the [Firestore Console](https://console.cloud.google.com/firestore).
2.  Create a database in Native mode.
3.  Select location: `europe-west2` (London).

## 3. Service Account Setup

Create a service account for Cloud Tasks to invoke Cloud Run:

```bash
gcloud iam service-accounts create maps-worker-sa \
  --display-name="MAPS Worker Service Account"

# Grant permissions to invoke Cloud Run
gcloud run services add-iam-policy-binding $SERVICE_NAME \
  --member="serviceAccount:maps-worker-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=$REGION
```

## 4. Cloud Tasks Queue

Create the queue in the correct region:

```bash
gcloud tasks queues create $QUEUE_NAME \
  --location=$REGION
```

## 5. Build and Deploy

### Option A: Cloud Build (Recommended)

Submit the build and deploy in one step:

```bash
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --service-account maps-worker-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars GCP_PROJECT_ID=$PROJECT_ID \
  --set-env-vars FIREBASE_PROJECT_ID=$PROJECT_ID \
  --set-env-vars TASK_QUEUE_PATH=projects/$PROJECT_ID/locations/$REGION/queues/$QUEUE_NAME \
  --set-env-vars ENVIRONMENT=prod \
  --set-env-vars VERTEX_AI_LOCATION=$REGION \
  --set-env-vars SERVICE_ACCOUNT_EMAIL=maps-worker-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### Option B: Manual Docker Build

1.  **Build Image**:
    ```bash
    docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME .
    ```

2.  **Push Image**:
    ```bash
    docker push gcr.io/$PROJECT_ID/$SERVICE_NAME
    ```

3.  **Deploy**:
    ```bash
    gcloud run deploy $SERVICE_NAME \
      --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
      --platform managed \
      --region $REGION \
      ... # (same flags as above)
    ```

## 6. Post-Deployment Configuration

After deployment, get your service URL:

```bash
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"
```

Update the `SERVICE_URL` environment variable if you didn't set it correctly during deployment (Cloud Tasks needs this to know where to send callbacks).

```bash
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --set-env-vars SERVICE_URL=$SERVICE_URL
```

## 7. Verification

Check the health endpoint:

```bash
curl $SERVICE_URL/health
curl $SERVICE_URL/readiness
```

## Troubleshooting

-   **503 Service Unavailable**: Check logs (`gcloud logging read ...`). Often due to missing environment variables or permissions.
-   **401 Unauthorized on Worker**: Ensure the Cloud Tasks queue is using the correct OIDC service account and that account has `run.invoker` role.
