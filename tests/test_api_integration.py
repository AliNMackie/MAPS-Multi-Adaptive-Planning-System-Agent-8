import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from src.main import app
from src.api.routes.analysis import get_db, get_queue

client = TestClient(app)

@pytest.fixture
def mock_auth():
    with patch("src.core.security.auth.verify_id_token") as mock:
        mock.return_value = {"tenant_id": "tenant-test"}
        yield mock

@pytest.fixture(autouse=True)
def mock_dependencies():
    """
    Mock DB and Queue for all tests to prevent real GCloud auth/connection attempts.
    """
    mock_db = MagicMock()
    mock_queue = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_queue] = lambda: mock_queue
    yield
    app.dependency_overrides = {}

def test_analyze_endpoint_with_auth(mock_auth):
    # Get the mock instances (since they are new each time lambda is called? No, lambda returns new mock?)
    # Wait, lambda: mock_db returns the SAME mock_db object defined in fixture?
    # No, the fixture defined mock_db but didn't expose it.
    # We need to access the mocks to verify calls.
    
    # Let's refine the fixture to return the mocks or set them on app.state or something.
    # Or just manually set overrides in test_analyze_endpoint_with_auth to access them.
    pass 

# Re-write tests to handle overrides properly

def test_analyze_endpoint_with_auth_refactored(mock_auth):
    mock_db = MagicMock()
    mock_queue = MagicMock()
    
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_queue] = lambda: mock_queue
    
    try:
        response = client.post(
            "/api/v1/analyze", 
            json={"contract_text": "test"},
            headers={"Authorization": "Bearer token"}
        )
        
        assert response.status_code == 202
        assert response.json()["status"] == "queued"
        
        # Verify DB interaction
        mock_db.collection.assert_called_once()
        args, _ = mock_db.collection.call_args
        assert "tenants/tenant-test/jobs" in args[0]
        
        # Verify Queue interaction
        mock_queue.enqueue_job.assert_called_once()
        
    finally:
        app.dependency_overrides = {}

def test_analyze_endpoint_no_auth():
    # Even if no auth, we mock DB to avoid GCloud error if dependency is resolved
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    try:
        response = client.post(
            "/api/v1/analyze", 
            json={"contract_text": "test"}
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides = {}
