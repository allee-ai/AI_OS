"""
Tests for API endpoints.

Tests:
- /api/subconscious/* endpoints
- /health endpoint
"""

import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestSubconsciousAPI:
    """Test subconscious API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from scripts.server import app
        return TestClient(app)
    
    def test_threads_endpoint(self, client):
        """/api/subconscious/threads should return thread info."""
        response = client.get("/api/subconscious/threads")
        
        assert response.status_code == 200
        data = response.json()
        # Returns dict with 'threads' key
        assert isinstance(data, dict)
        assert "threads" in data
    
    def test_build_state_endpoint(self, client):
        """/api/subconscious/build_state should return STATE."""
        response = client.get("/api/subconscious/build_state?query=hello")
        
        assert response.status_code == 200
        data = response.json()
        assert "state" in data or isinstance(data, str)


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from scripts.server import app
        return TestClient(app)
    
    def test_health_returns_ok(self, client):
        """/health should return OK status."""
        response = client.get("/health")
        
        assert response.status_code == 200
