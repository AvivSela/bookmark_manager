# Bookmark Service

A FastAPI-based REST API service for managing bookmarks with full CRUD operations, pagination, and sorting capabilities.

## Features

- **Full CRUD Operations**: Create, Read, Update, and Delete bookmarks
- **Pagination**: Efficient pagination with configurable page sizes
- **Sorting**: Sort by created_time, changed_time, or title in ascending/descending order
- **URL Validation**: Automatic validation of bookmark URLs
- **Unique Constraints**: Prevents duplicate URLs
- **PostgreSQL**: Production database with async support
- **Auto-generated Docs**: Interactive API documentation via Swagger UI and ReDoc
- **Health Check Endpoint**: Monitor service status
- **Comprehensive Tests**: Full test suite with SQLite in-memory database

## Tech Stack

- **Framework**: FastAPI 0.109.0
- **Database**: PostgreSQL (production), SQLite (testing)
- **ORM**: SQLAlchemy 2.0.25 (async)
- **Validation**: Pydantic 2.5.3
- **Server**: Uvicorn
- **Testing**: pytest, pytest-asyncio, httpx

## Project Structure

```
bookmark_service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration and settings
│   ├── database.py          # Database connection and session management
│   ├── models/
│   │   ├── __init__.py
│   │   └── bookmark.py      # SQLAlchemy bookmark model
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── bookmark.py      # Pydantic schemas for validation
│   └── routes/
│       ├── __init__.py
│       ├── bookmarks.py     # Bookmark CRUD endpoints
│       └── health.py        # Health check endpoint
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures and configuration
│   ├── test_bookmark_crud.py
│   ├── test_pagination.py
│   └── test_validation.py
├── .env.test                # Test environment variables
├── requirements.txt         # Python dependencies
├── pytest.ini              # Pytest configuration
├── run_tests.sh            # Convenience script for running tests
└── Dockerfile              # Multi-stage production Docker build
```

## API Endpoints

### Bookmarks

- `POST /bookmarks` - Create a new bookmark
- `GET /bookmarks` - List all bookmarks (with pagination and sorting)
- `GET /bookmarks/{bookmark_id}` - Get a specific bookmark
- `PUT /bookmarks/{bookmark_id}` - Update a bookmark
- `DELETE /bookmarks/{bookmark_id}` - Delete a bookmark

### Other

- `GET /` - API information
- `GET /health` - Health check endpoint
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

## Quick Start

### Running with Docker Compose

From the project root:

```bash
docker compose up bookmark-service
```

The service will be available at `http://localhost:8000`

### Running Locally (Development)

1. **Set up Python environment**:

```bash
cd services/bookmark_service

# Create virtual environment with uv
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

2. **Set up environment variables**:

```bash
# Copy and edit the example env file
cp ../../.env.example ../../.env

# Or set variables directly
export POSTGRES_USER=bookmark_user
export POSTGRES_PASSWORD=bookmark_pass
export POSTGRES_DB=bookmark_db
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
```

3. **Ensure PostgreSQL is running**:

```bash
# Using docker compose (recommended)
docker compose up postgres -d

# Or use a local PostgreSQL installation
```

4. **Run the service**:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Testing

The test suite uses SQLite in-memory database for fast, isolated tests without requiring Docker or PostgreSQL.

### Run all tests

```bash
./run_tests.sh
```

### Run specific test file

```bash
./run_tests.sh tests/test_pagination.py
```

### Run with coverage

```bash
./run_tests.sh --cov=app --cov-report=html
```

### Run with verbose output

```bash
./run_tests.sh -v
```

### Manual test execution

```bash
# Load test environment variables
set -a; source .env.test; set +a

# Run tests
.venv/bin/pytest tests/ -v
```

## Configuration

Configuration is managed through environment variables defined in [app/config.py](app/config.py):

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | Database username | Required |
| `POSTGRES_PASSWORD` | Database password | Required |
| `POSTGRES_DB` | Database name | Required |
| `POSTGRES_HOST` | Database host | `postgres` |
| `POSTGRES_PORT` | Database port | `5432` |
| `DEBUG` | Debug mode | `false` |

## API Usage Examples

### Create a bookmark

```bash
curl -X POST http://localhost:8000/bookmarks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "title": "Example Site",
    "description": "An example website"
  }'
```

### List bookmarks with pagination

```bash
curl "http://localhost:8000/bookmarks?page=1&page_size=10&sort_by=created_time&sort_order=desc"
```

### Get a specific bookmark

```bash
curl http://localhost:8000/bookmarks/{bookmark_id}
```

### Update a bookmark

```bash
curl -X PUT http://localhost:8000/bookmarks/{bookmark_id} \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Title"
  }'
```

### Delete a bookmark

```bash
curl -X DELETE http://localhost:8000/bookmarks/{bookmark_id}
```

## Database Schema

### Bookmark Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key (auto-generated) |
| `url` | String | Bookmark URL (unique, required) |
| `title` | String | Bookmark title (1-500 chars, required) |
| `description` | String | Optional description (max 5000 chars) |
| `created_time` | DateTime | Timestamp when created (auto-generated) |
| `changed_time` | DateTime | Timestamp when last updated (auto-updated) |

## Development

### Code Quality

The codebase follows these principles:
- Type hints for all functions
- Comprehensive docstrings
- Input validation using Pydantic
- Async/await for database operations
- Proper error handling with HTTP status codes

### Adding New Endpoints

1. Add route handler in [app/routes/bookmarks.py](app/routes/bookmarks.py)
2. Define schemas in [app/schemas/bookmark.py](app/schemas/bookmark.py) if needed
3. Add tests in `tests/`
4. Update this README if adding major features

## Troubleshooting

### Tests fail with "Settings validation error"

Make sure you're using the test script or loading environment variables:

```bash
./run_tests.sh
# OR
set -a; source .env.test; set +a
pytest
```

### Database connection errors

Ensure PostgreSQL is running and environment variables are set correctly:

```bash
docker compose up postgres -d
docker compose ps
```

### Port already in use

Change the port in docker-compose.yml or kill the process using port 8000:

```bash
lsof -ti:8000 | xargs kill -9
```

## License

This project is part of the bookmark management system.
