#!/usr/bin/env python3
"""
Script to drop and recreate all database tables with the new schema.

WARNING: This will DELETE ALL DATA in the bookmarks table!
Only use this in development/testing environments.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine, Base
from app.models.bookmark import Bookmark  # Import to register with Base


async def recreate_tables():
    """Drop and recreate all tables."""
    print("=" * 60)
    print("WARNING: This will DELETE ALL DATA!")
    print("=" * 60)
    print()
    print("Dropping all tables...")

    async with engine.begin() as conn:
        # Drop all tables
        await conn.run_sync(Base.metadata.drop_all)
        print("✓ All tables dropped successfully")

    print()
    print("Creating all tables with new schema...")

    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        print("✓ All tables created successfully")

    print()
    print("=" * 60)
    print("Database schema updated!")
    print("=" * 60)
    print()
    print("Bookmarks table schema:")
    print("  - enrichments (JSONB) - All enrichment data in single JSON column")
    print("  - resource_type (String) - For filtering/querying")
    print("  - validation_* fields - For status tracking")
    print("  - idx_resource_type (Index)")
    print()
    print("Removed individual enrichment columns:")
    print("  - og_title, og_description, og_image, og_type, og_site_name")
    print("  - meta_description, favicon_url, screenshot_url")
    print("  - api_metadata, dataset_metadata, media_metadata")
    print()


async def main():
    """Main entry point."""
    try:
        await recreate_tables()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Dispose engine
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
