# 🇬🇧 UK/EU Infrastructure Cheat Sheet (DeckSmith)

## 🚨 The 3 Golden Rules
1.  **Region:** ALWAYS use `europe-west2` (London).
2.  **Access:** NO public IPs. NO `allUsers`.
3.  **Safety:** `deletion_protection = true` on ALL databases.

## 🏗️ Approved Patterns (Copy-Paste Ready)

### A. Public Web Service (Secure)
* **Pattern:** LB -> Cloud Armor -> Cloud Run (Internal Ingress)
* **Terraform Snippet:**
    ```hcl
    resource "google_cloud_run_service" "app" {
      location = "europe-west2"
      template {
        spec {
          containers { image = "gcr.io/..." }
        }
      }
      metadata {
        annotations = {
          "[run.googleapis.com/ingress](https://run.googleapis.com/ingress)" = "internal-and-cloud-load-balancing"
        }
      }
    }
    ```

### B. Private Worker (Async)
* **Pattern:** Pub/Sub -> Cloud Function (Gen 2) -> Cloud SQL
* **Requirement:** Function must attach to a VPC Connector to reach SQL.

### C. Secure Bucket (GDPR)
* **Pattern:** Private + CMEK + Versioning
* **Terraform Snippet:**
    ```hcl
    resource "google_storage_bucket" "secure_store" {
      location                    = "europe-west2"
      uniform_bucket_level_access = true
      public_access_prevention    = "enforced"
      versioning { enabled = true }
    }
    ```