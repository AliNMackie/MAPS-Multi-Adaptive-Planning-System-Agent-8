import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request, Depends, status
from fastapi.testclient import TestClient
from src.core.security import tenant_scoped, SecurityBreachError, current_tenant
from src.core.firestore_wrapper import TenantFirestore

# Mock firebase_admin
with patch("firebase_admin.auth.verify_id_token") as mock_verify:
    pass # Just to ensure we can patch it in tests

# Create a simple FastAPI app for testing middleware
app = FastAPI()

@app.get("/data")
@tenant_scoped
async def get_data(request: Request):
    return {"tenant": current_tenant.get(), "message": "Success"}

@app.get("/db-test")
@tenant_scoped
async def db_test(request: Request, path: str):
    mock_client = MagicMock()
    mock_col_ref = MagicMock()
    mock_client.collection.return_value = mock_col_ref
    
    db = TenantFirestore(client=mock_client)
    col = db.collection(path)
    return {"path": path, "status": "accessed"}

client = TestClient(app)

def test_tenant_isolation_middleware_success():
    with patch("src.core.security.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = {"tenant_id": "tenant-123"}
        response = client.get("/data", headers={"Authorization": "Bearer valid-token"})
        assert response.status_code == 200
        assert response.json()["tenant"] == "tenant-123"

def test_tenant_isolation_middleware_no_token():
    response = client.get("/data")
    assert response.status_code == 403

def test_tenant_isolation_middleware_invalid_token():
    with patch("src.core.security.auth.verify_id_token") as mock_verify:
        mock_verify.side_effect = Exception("Invalid token")
        response = client.get("/data", headers={"Authorization": "Bearer bad-token"})
        assert response.status_code == 403

def test_firestore_wrapper_valid_access():
    token = current_tenant.set("tenant-A")
    try:
        mock_real_client = MagicMock()
        db = TenantFirestore(client=mock_real_client)
        db.collection("tenants/tenant-A/users")
        mock_real_client.collection.assert_called_with("tenants/tenant-A/users")
    finally:
        current_tenant.reset(token)

def test_firestore_wrapper_cross_tenant_access_hack():
    token = current_tenant.set("tenant-A")
    try:
        mock_real_client = MagicMock()
        db = TenantFirestore(client=mock_real_client)
        with pytest.raises(SecurityBreachError):
            db.collection("tenants/tenant-B/users")
        with pytest.raises(SecurityBreachError):
            db.collection("users")
    finally:
        current_tenant.reset(token)

def test_firestore_wrapper_traversal_attack():
    token = current_tenant.set("tenant-A")
    try:
        mock_real_client = MagicMock()
        
        # Setup mock hierarchy
        # tenants/tenant-A/users/doc1
        mock_doc_ref = MagicMock()
        mock_doc_ref.path = "tenants/tenant-A/users/doc1"
        
        mock_col_ref = MagicMock()
        mock_col_ref.path = "tenants/tenant-A/users"
        mock_col_ref.document.return_value = mock_doc_ref
        
        mock_real_client.collection.return_value = mock_col_ref
        
        # Parent of doc is collection (safe)
        mock_doc_ref.parent = mock_col_ref
        
        # Parent of collection is doc? No, parent of collection is doc or None (if root).
        # Wait, firestore hierarchy: Collection -> Doc -> Collection -> Doc
        # tenants/tenant-A (doc) -> users (col) -> doc1 (doc)
        
        mock_tenant_doc = MagicMock()
        mock_tenant_doc.path = "tenants/tenant-A"
        mock_col_ref.parent = mock_tenant_doc
        
        mock_root_col = MagicMock()
        mock_root_col.path = "tenants"
        mock_tenant_doc.parent = mock_root_col
        
        db = TenantFirestore(client=mock_real_client)
        
        # Get valid collection
        col = db.collection("tenants/tenant-A/users")
        
        # Get valid doc
        doc = col.document("doc1")
        
        # Access parent (collection) - Should be OK
        parent_col = doc.parent
        assert parent_col._ref.path == "tenants/tenant-A/users"
        
        # Access parent of collection (tenant doc) - Should be OK?
        # tenants/tenant-A is the prefix.
        parent_doc = parent_col.parent
        assert parent_doc._ref.path == "tenants/tenant-A"
        
        # Access parent of tenant doc (tenants collection) - Should FAIL
        # Path "tenants" does not start with "tenants/tenant-A/"
        with pytest.raises(SecurityBreachError) as excinfo:
            _ = parent_doc.parent
        assert "Traversal attempt denied" in str(excinfo.value)

    finally:
        current_tenant.reset(token)

def test_firestore_wrapper_add_check():
    token = current_tenant.set("tenant-A")
    try:
        mock_real_client = MagicMock()
        mock_col_ref = MagicMock()
        mock_col_ref.path = "tenants/tenant-A/users"
        mock_real_client.collection.return_value = mock_col_ref
        
        # Mock add behavior
        mock_new_doc_ref = MagicMock()
        mock_new_doc_ref.path = "tenants/tenant-A/users/new_id"
        mock_col_ref.document.return_value = mock_new_doc_ref
        
        mock_new_doc_ref.create.return_value = "timestamp"
        
        db = TenantFirestore(client=mock_real_client)
        col = db.collection("tenants/tenant-A/users")
        
        # Should succeed
        col.add({"name": "test"})
        
        # Verify create was called
        mock_new_doc_ref.create.assert_called()

    finally:
        current_tenant.reset(token)

def test_batch_wrapper_usage():
    token = current_tenant.set("tenant-A")
    try:
        mock_real_client = MagicMock()
        mock_batch = MagicMock()
        mock_real_client.batch.return_value = mock_batch
        
        db = TenantFirestore(client=mock_real_client)
        batch = db.batch()
        
        # Mock refs
        doc_ref = MagicMock()
        doc_ref.path = "tenants/tenant-A/users/1"
        
        # Wrap doc ref? batch accepts unwrapped or wrapped? 
        # Our batch wrapper unwraps if needed.
        # If we pass a mock directly with path, it checks path.
        
        batch.set(doc_ref, {"a": 1})
        mock_batch.set.assert_called()
        
        # Invalid ref
        bad_ref = MagicMock()
        bad_ref.path = "tenants/tenant-B/users/1"
        del bad_ref._ref # Ensure it doesn't have _ref so validation happens on bad_ref
        with pytest.raises(SecurityBreachError):
            batch.set(bad_ref, {"a": 1})

    finally:
        current_tenant.reset(token)

def test_endpoint_hack_attempt():
    with patch("src.core.security.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = {"tenant_id": "tenant-A"}
        
        # valid
        response = client.get("/db-test?path=tenants/tenant-A/data", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        
        # invalid (hack)
        # Because we fixed security.py to propagate exceptions for logic (SecurityBreachError) 
        # but catch auth errors.
        # Wait, I updated security.py to catch verify_token exceptions, then set context, then call func.
        # The SecurityBreachError happens in func.
        # Func is called inside `try: ... finally: reset`.
        # So SecurityBreachError propagates out of decorator.
        # FastAPI default exception handler returns 500.
        
        try:
            response = client.get("/db-test?path=tenants/tenant-B/data", headers={"Authorization": "Bearer token"})
            assert response.status_code == 500
        except SecurityBreachError:
            pass # Depending on TestClient config
