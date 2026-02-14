"""
Root-level conftest for E2E tests.

These fixtures require the full infrastructure to be running.
"""

import os
import pytest

# E2E test configuration
E2E_BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture
def base_url() -> str:
    """Return the base URL for E2E tests."""
    return E2E_BASE_URL


@pytest.fixture
def e2e_user_credentials() -> dict:
    """Generate unique credentials for E2E test user."""
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    return {
        "email": f"e2e_test_{unique_id}@example.com",
        "password": "E2eTestP@ss123",
        "name": f"E2E Test User {unique_id}",
    }
