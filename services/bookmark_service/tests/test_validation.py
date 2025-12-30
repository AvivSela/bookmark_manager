import pytest
from httpx import AsyncClient


class TestBookmarkValidation:
    """Tests for Pydantic schema validation on bookmark fields."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invalid_url",
        [
            "not-a-url",
            "ftp://example.com",  # Only HTTP/HTTPS allowed
            "example.com",  # Missing protocol
            "",  # Empty string
            "htp://typo.com",  # Typo in protocol
        ],
    )
    async def test_create_bookmark_invalid_url_format_returns_400(
        self, client: AsyncClient, invalid_url: str
    ):
        """
        Test 6: Pydantic URL validation rejects malformed URLs.

        First line of defense against bad data - prevents invalid URLs from entering the system.
        """
        bookmark_data = {
            "url": invalid_url,
            "title": "Test Bookmark",
            "description": "Test description",
        }

        response = await client.post("/bookmarks", json=bookmark_data)

        # Custom validation error handler returns 400
        assert response.status_code == 400
        error_detail = response.json()
        assert "detail" in error_detail

    @pytest.mark.asyncio
    async def test_create_bookmark_title_exceeds_max_length_returns_400(
        self, client: AsyncClient
    ):
        """
        Test 7: Title field length constraint (max 500 chars) is enforced.

        Ensures database constraints match application validation - prevents truncation errors.
        """
        bookmark_data = {
            "url": "https://example.com",
            "title": "a" * 501,  # 501 characters, exceeds max of 500
            "description": "Test description",
        }

        response = await client.post("/bookmarks", json=bookmark_data)

        # Custom validation error handler returns 400
        assert response.status_code == 400
        error_detail = response.json()
        assert "detail" in error_detail

        # Check that the error is about title length
        error_message = str(error_detail["detail"])
        assert "title" in error_message.lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "empty_title",
        [
            "",  # Empty string
            "   ",  # Whitespace only
        ],
    )
    async def test_create_bookmark_empty_title_returns_400(
        self, client: AsyncClient, empty_title: str
    ):
        """
        Test 8: Title field is required and cannot be empty.

        Title is a required business field - empty titles break user experience.
        """
        bookmark_data = {
            "url": "https://example.com",
            "title": empty_title,
            "description": "Test description",
        }

        response = await client.post("/bookmarks", json=bookmark_data)

        # Custom validation error handler returns 400
        assert response.status_code == 400
        error_detail = response.json()
        assert "detail" in error_detail

        # Check that the error is about title
        error_message = str(error_detail["detail"])
        assert "title" in error_message.lower()

    @pytest.mark.asyncio
    async def test_create_bookmark_description_exceeds_max_length_returns_400(
        self, client: AsyncClient
    ):
        """
        Test 9: Description field length constraint (max 5000 chars) is enforced.

        Prevents excessively large payloads and database storage issues.
        """
        bookmark_data = {
            "url": "https://example.com",
            "title": "Test Bookmark",
            "description": "a" * 5001,  # 5001 characters, exceeds max of 5000
        }

        response = await client.post("/bookmarks", json=bookmark_data)

        # Custom validation error handler returns 400
        assert response.status_code == 400
        error_detail = response.json()
        assert "detail" in error_detail

        # Check that the error is about description length
        error_message = str(error_detail["detail"])
        assert "description" in error_message.lower()

    @pytest.mark.asyncio
    async def test_create_bookmark_valid_data_succeeds(self, client: AsyncClient):
        """
        Additional test: Verify that valid data passes all validation checks.

        This confirms that our validation tests aren't rejecting everything.
        """
        bookmark_data = {
            "url": "https://example.com",
            "title": "Valid Bookmark",
            "description": "This is a valid description",
        }

        response = await client.post("/bookmarks", json=bookmark_data)
        assert response.status_code == 201

        # Verify returned data
        bookmark = response.json()
        # Pydantic's HttpUrl adds trailing slash - compare normalized URLs
        assert bookmark["url"].rstrip("/") == bookmark_data["url"].rstrip("/")
        assert bookmark["title"] == bookmark_data["title"]
        assert bookmark["description"] == bookmark_data["description"]

    @pytest.mark.asyncio
    async def test_create_bookmark_without_description_succeeds(
        self, client: AsyncClient
    ):
        """
        Additional test: Description is optional - bookmark can be created without it.
        """
        bookmark_data = {
            "url": "https://example.com",
            "title": "Bookmark Without Description",
        }

        response = await client.post("/bookmarks", json=bookmark_data)
        assert response.status_code == 201

        # Verify description is None
        bookmark = response.json()
        assert bookmark["description"] is None

    @pytest.mark.asyncio
    async def test_create_bookmark_with_max_valid_title_length(
        self, client: AsyncClient
    ):
        """
        Additional test: Verify that max valid title length (500 chars) is accepted.
        """
        bookmark_data = {
            "url": "https://example.com",
            "title": "a" * 500,  # Exactly 500 characters
            "description": "Test",
        }

        response = await client.post("/bookmarks", json=bookmark_data)
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_bookmark_with_max_valid_description_length(
        self, client: AsyncClient
    ):
        """
        Additional test: Verify that max valid description length (5000 chars) is accepted.
        """
        bookmark_data = {
            "url": "https://example.com",
            "title": "Test Bookmark",
            "description": "a" * 5000,  # Exactly 5000 characters
        }

        response = await client.post("/bookmarks", json=bookmark_data)
        assert response.status_code == 201
