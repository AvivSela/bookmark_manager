import pytest
from app.validators.url_validator import URLValidator


@pytest.fixture
def validator():
    """Create URLValidator instance for testing."""
    return URLValidator()


@pytest.fixture
def mock_bookmark_id():
    """Generate a test bookmark UUID."""
    from uuid import uuid4

    return uuid4()
