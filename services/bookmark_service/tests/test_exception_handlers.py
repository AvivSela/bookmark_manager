from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


class TestHTTPExceptionHandler:
    """Tests for custom HTTPException handler."""

    @pytest.mark.asyncio
    async def test_http_exception_includes_request_id_in_response(
        self, client: AsyncClient
    ):
        """
        Test that HTTPException handler includes X-Request-ID in error response.

        Validates:
        1. X-Request-ID header is present in error response
        2. Request ID matches the one from the request
        3. Error response format is correct
        4. Status code is preserved from the HTTPException
        """
        # Create a request with a custom request ID
        custom_request_id = "test-request-12345"

        # Trigger an HTTPException by requesting without X-Tenant-ID header
        # This will raise HTTP 401 from dependencies.py
        # We need to create a client without X-Tenant-ID header
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Request-ID": custom_request_id},
        ) as test_client:
            response = await test_client.get("/bookmarks")

        # Assert HTTP 401 is returned
        assert response.status_code == 401

        # Assert X-Request-ID is in response headers
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] == custom_request_id

        # Assert error response format
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], str)

    @pytest.mark.asyncio
    async def test_http_exception_generates_request_id_if_not_provided(
        self, client: AsyncClient
    ):
        """
        Test that HTTPException handler generates X-Request-ID if not in request.

        The middleware generates a UUID if X-Request-ID is not provided.
        """
        # Trigger HTTPException without providing X-Request-ID
        # Note: client fixture includes X-Tenant-ID, so we need to remove it
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as bare_client:
            response = await bare_client.get("/bookmarks")

        # Assert HTTP 401 is returned
        assert response.status_code == 401

        # Assert X-Request-ID was generated and included
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_http_404_exception_includes_request_id(self, client: AsyncClient):
        """
        Test that HTTP 404 errors include X-Request-ID.

        Tests the handler with a different status code (404 vs 401).
        """
        custom_request_id = "test-request-404"

        # Request a non-existent bookmark with a valid UUID
        # This UUID won't exist in the test database
        non_existent_uuid = "00000000-0000-0000-0000-000000000001"
        response = await client.get(
            f"/bookmarks/{non_existent_uuid}",
            headers={"X-Request-ID": custom_request_id},
        )

        # Assert HTTP 404 is returned
        assert response.status_code == 404

        # Assert X-Request-ID is in response
        assert response.headers["X-Request-ID"] == custom_request_id

        # Assert error format
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_http_exception_handler_logs_with_appropriate_level(
        self, client: AsyncClient
    ):
        """
        Test that HTTPException handler logs with appropriate level.

        - 4xx errors: logger.warning
        - 5xx errors: logger.error
        """
        from app.main import app

        with patch("app.validation_exception_handler.logger") as mock_logger:
            # Trigger a 4xx error (401)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as test_client:
                await test_client.get("/bookmarks")

            # Assert warning was logged for 4xx
            mock_logger.warning.assert_called_once()
            log_call = mock_logger.warning.call_args[0][0]
            assert "401" in log_call or "status_code=401" in log_call
