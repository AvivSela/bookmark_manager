import pytest
from httpx import AsyncClient
import asyncio


class TestBookmarkPagination:
    """Tests for pagination and sorting functionality on bookmark list endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("total_items,page_size,expected_pages", [
        (0, 10, 0),    # No items
        (1, 10, 1),    # Single item
        (10, 10, 1),   # Exact multiple
        (11, 10, 2),   # With remainder
        (99, 10, 10),  # Multiple pages
        (100, 10, 10), # Exact multiple, larger dataset
        (5, 3, 2),     # Small page size
    ])
    async def test_list_bookmarks_pagination_calculates_total_pages_correctly(
        self, client: AsyncClient, total_items: int, page_size: int, expected_pages: int
    ):
        """
        Test 10: Total pages calculation for various combinations of items and page sizes.

        Incorrect pagination math breaks client-side UI - edge cases are common sources
        of off-by-one errors.
        """
        # Create the specified number of bookmarks
        for i in range(total_items):
            bookmark_data = {
                "url": f"https://example{i}.com",
                "title": f"Bookmark {i}",
                "description": f"Description {i}"
            }
            create_response = await client.post("/bookmarks", json=bookmark_data)
            assert create_response.status_code == 201

        # Request the list with specified page size
        response = await client.get(f"/bookmarks?page=1&page_size={page_size}")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == total_items
        assert data["total_pages"] == expected_pages
        assert data["page_size"] == page_size

        # Verify items returned don't exceed page_size
        assert len(data["items"]) <= page_size

    @pytest.mark.asyncio
    async def test_list_bookmarks_respects_page_size_limit(self, client: AsyncClient):
        """
        Test 11: Page size cannot exceed max_page_size (100).

        Prevents performance degradation from oversized queries - protects from
        resource exhaustion.
        """
        # Create some bookmarks
        for i in range(5):
            bookmark_data = {
                "url": f"https://example{i}.com",
                "title": f"Bookmark {i}",
            }
            await client.post("/bookmarks", json=bookmark_data)

        # Request with page_size exceeding limit (150 > 100)
        response = await client.get("/bookmarks?page=1&page_size=150")

        # Custom validation error handler returns 400
        assert response.status_code == 400
        error_detail = response.json()
        assert "detail" in error_detail

    @pytest.mark.asyncio
    async def test_list_bookmarks_sort_order_ascending_and_descending(
        self, client: AsyncClient
    ):
        """
        Test 12: Sort order (asc/desc) is correctly applied to results.

        Users rely on sorting to find bookmarks - incorrect order breaks workflows.
        """
        # Create 3 bookmarks with delays to ensure different timestamps
        bookmarks = []
        for i in range(3):
            bookmark_data = {
                "url": f"https://example{i}.com",
                "title": f"Bookmark {i}",
            }
            response = await client.post("/bookmarks", json=bookmark_data)
            assert response.status_code == 201
            bookmarks.append(response.json())
            await asyncio.sleep(0.05)  # Small delay to ensure different timestamps

        # Test ascending order (oldest first)
        response_asc = await client.get(
            "/bookmarks?sort_by=created_time&sort_order=asc&page_size=10"
        )
        assert response_asc.status_code == 200
        data_asc = response_asc.json()
        items_asc = data_asc["items"]

        # Verify ascending order
        assert len(items_asc) == 3
        assert items_asc[0]["id"] == bookmarks[0]["id"]  # Oldest first
        assert items_asc[1]["id"] == bookmarks[1]["id"]
        assert items_asc[2]["id"] == bookmarks[2]["id"]  # Newest last

        # Test descending order (newest first)
        response_desc = await client.get(
            "/bookmarks?sort_by=created_time&sort_order=desc&page_size=10"
        )
        assert response_desc.status_code == 200
        data_desc = response_desc.json()
        items_desc = data_desc["items"]

        # Verify descending order
        assert len(items_desc) == 3
        assert items_desc[0]["id"] == bookmarks[2]["id"]  # Newest first
        assert items_desc[1]["id"] == bookmarks[1]["id"]
        assert items_desc[2]["id"] == bookmarks[0]["id"]  # Oldest last

    @pytest.mark.asyncio
    async def test_list_bookmarks_sort_by_different_fields(self, client: AsyncClient):
        """
        Test 13: Sorting works correctly for all allowed fields
        (created_time, changed_time, title).

        Each sort field serves different use cases - ensures all advertised options work.
        """
        # Create bookmarks with distinct values for sorting
        bookmark_data_list = [
            {"url": "https://c-site.com", "title": "Charlie"},
            {"url": "https://a-site.com", "title": "Alpha"},
            {"url": "https://b-site.com", "title": "Beta"},
        ]

        created_bookmarks = []
        for data in bookmark_data_list:
            response = await client.post("/bookmarks", json=data)
            assert response.status_code == 201
            created_bookmarks.append(response.json())
            await asyncio.sleep(0.05)  # Ensure different timestamps

        # Test 1: Sort by created_time (default desc)
        response_created = await client.get(
            "/bookmarks?sort_by=created_time&sort_order=desc&page_size=10"
        )
        assert response_created.status_code == 200
        items_created = response_created.json()["items"]
        # Should be in reverse creation order (Beta, Alpha, Charlie)
        assert items_created[0]["title"] == "Beta"
        assert items_created[1]["title"] == "Alpha"
        assert items_created[2]["title"] == "Charlie"

        # Test 2: Sort by title (alphabetical ascending)
        response_title = await client.get(
            "/bookmarks?sort_by=title&sort_order=asc&page_size=10"
        )
        assert response_title.status_code == 200
        items_title = response_title.json()["items"]
        # Should be alphabetical (Alpha, Beta, Charlie)
        assert items_title[0]["title"] == "Alpha"
        assert items_title[1]["title"] == "Beta"
        assert items_title[2]["title"] == "Charlie"

        # Test 3: Sort by changed_time
        # First, update the first bookmark to change its changed_time
        first_bookmark_id = created_bookmarks[0]["id"]
        await asyncio.sleep(0.1)  # Ensure time difference
        update_response = await client.put(
            f"/bookmarks/{first_bookmark_id}",
            json={"title": "Charlie Updated"}
        )
        assert update_response.status_code == 200

        # Now sort by changed_time desc - the updated one should be first
        response_changed = await client.get(
            "/bookmarks?sort_by=changed_time&sort_order=desc&page_size=10"
        )
        assert response_changed.status_code == 200
        items_changed = response_changed.json()["items"]
        # The updated bookmark should be first (most recently changed)
        assert items_changed[0]["title"] == "Charlie Updated"

    @pytest.mark.asyncio
    async def test_list_bookmarks_pagination_returns_correct_page(
        self, client: AsyncClient
    ):
        """
        Additional test: Verify that requesting different pages returns correct items.
        """
        # Create 25 bookmarks
        for i in range(25):
            bookmark_data = {
                "url": f"https://example{i}.com",
                "title": f"Bookmark {i:02d}",  # Zero-padded for consistent sorting
            }
            await client.post("/bookmarks", json=bookmark_data)

        # Request page 1 with page_size=10
        response_page1 = await client.get("/bookmarks?page=1&page_size=10")
        assert response_page1.status_code == 200
        data_page1 = response_page1.json()
        assert data_page1["page"] == 1
        assert len(data_page1["items"]) == 10
        assert data_page1["total"] == 25
        assert data_page1["total_pages"] == 3

        # Request page 2 with page_size=10
        response_page2 = await client.get("/bookmarks?page=2&page_size=10")
        assert response_page2.status_code == 200
        data_page2 = response_page2.json()
        assert data_page2["page"] == 2
        assert len(data_page2["items"]) == 10

        # Request page 3 with page_size=10 (last page, partial)
        response_page3 = await client.get("/bookmarks?page=3&page_size=10")
        assert response_page3.status_code == 200
        data_page3 = response_page3.json()
        assert data_page3["page"] == 3
        assert len(data_page3["items"]) == 5  # Only 5 items on last page

        # Verify items on different pages are different
        page1_ids = {item["id"] for item in data_page1["items"]}
        page2_ids = {item["id"] for item in data_page2["items"]}
        assert page1_ids.isdisjoint(page2_ids)  # No overlap

    @pytest.mark.asyncio
    async def test_list_bookmarks_empty_list(self, client: AsyncClient):
        """
        Additional test: Verify empty list handling with no bookmarks.
        """
        response = await client.get("/bookmarks?page=1&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["total_pages"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 10
