# Bookmark Service

A FastAPI-based REST API service for managing bookmarks with full CRUD operations, pagination, and sorting capabilities.

## Features

- **Full CRUD Operations**: Create, Read, Update, and Delete bookmarks
- **Multi-tenancy**: User-scoped bookmarks with user_id field
- **Pagination**: Efficient pagination with configurable page sizes
- **Sorting**: Sort by created_time, changed_time, or title in ascending/descending order
- **URL Validation**: Automatic validation of bookmark URLs
- **Unique Constraints**: Prevents duplicate URLs per user
- **Kafka Event Publishing**: Publishes bookmark.created events for downstream services
- **Enrichment Support**: Stores Open Graph metadata (title, description, image, etc.)
- **Validation Tracking**: Tracks URL validation status and results
- **PostgreSQL**: Production database with async support
- **Auto-generated Docs**: Interactive API documentation via Swagger UI and ReDoc
- **Health Check Endpoint**: Monitor service status
- **Comprehensive Tests**: Full test suite with SQLite in-memory database

## Tech Stack

- **Framework**: FastAPI 0.109.0
- **Database**: PostgreSQL (production), SQLite (testing)
- **ORM**: SQLAlchemy 2.0.25 (async)
- **Validation**: Pydantic 2.5.3
- **Message Broker**: Kafka (via aiokafka)
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
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── bookmarks.py     # Bookmark CRUD endpoints
│   │   └── health.py        # Health check endpoint
│   └── kafka/
│       ├── __init__.py
│       ├── producer.py      # Kafka event producer
│       └── schemas.py       # Kafka event schemas
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures and configuration
│   ├── test_bookmark_crud.py
│   ├── test_pagination.py
│   ├── test_validation.py
│   └── test_kafka_events.py # Kafka integration tests
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
| **Database** | | |
| `POSTGRES_USER` | Database username | Required |
| `POSTGRES_PASSWORD` | Database password | Required |
| `POSTGRES_DB` | Database name | Required |
| `POSTGRES_HOST` | Database host | `postgres` |
| `POSTGRES_PORT` | Database port | `5432` |
| **Kafka** | | |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `bookmark-kafka:9092` |
| `KAFKA_TOPIC_PREFIX` | Topic prefix for events | `bookmarks` |
| `KAFKA_ENABLED` | Enable/disable Kafka publishing | `true` |
| `KAFKA_COMPRESSION_TYPE` | Event compression type | `gzip` |
| `KAFKA_MAX_RETRIES` | Max retry attempts for publishing | `3` |
| `KAFKA_REQUEST_TIMEOUT_MS` | Kafka request timeout | `30000` |
| **Application** | | |
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
| **Core Fields** | | |
| `id` | UUID | Primary key (auto-generated) |
| `user_id` | String | User identifier for multi-tenancy (required, indexed) |
| `url` | String | Bookmark URL (max 2048 chars, required, indexed) |
| `title` | String | Bookmark title (1-500 chars, required) |
| `description` | Text | Optional description (max 5000 chars) |
| `created_time` | DateTime | Timestamp when created (auto-generated, indexed) |
| `changed_time` | DateTime | Timestamp when last updated (auto-updated) |
| **Enrichment Fields** | | |
| `og_title` | String | Open Graph title (max 500 chars) |
| `og_description` | Text | Open Graph description (max 5000 chars) |
| `og_image` | String | Open Graph image URL (max 2048 chars) |
| `og_type` | String | Open Graph type (max 100 chars) |
| `og_site_name` | String | Open Graph site name (max 200 chars) |
| `meta_description` | Text | Meta description fallback (max 5000 chars) |
| `favicon_url` | String | Favicon URL (max 2048 chars) |
| **Validation Fields** | | |
| `validation_status` | String | Status: 'valid', 'invalid', 'pending', 'error' (max 20 chars, indexed) |
| `validation_last_checked` | DateTime | Last validation timestamp (indexed) |
| `validation_http_status` | Integer | HTTP status code from validation |
| `validation_final_url` | String | Final URL after redirects (max 2048 chars) |
| `validation_error_message` | Text | Error details if validation failed |

**Indexes:**
- `idx_bookmark_created_time` on `created_time`
- `idx_user_bookmarks` on `(user_id, created_time)`
- `idx_validation_status` on `validation_status`
- `idx_validation_last_checked` on `validation_last_checked`
- `idx_pending_validation` on `(validation_status, validation_last_checked)`

**Constraints:**
- `uq_user_url`: Unique constraint on `(user_id, url)` - prevents duplicate URLs per user

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

### Kafka Event Publishing

The service publishes events to Kafka when bookmarks are created:

**Topic:** `bookmarks.bookmark.created`

**Event Schema:**
```json
{
  "event_id": "uuid",
  "event_type": "bookmark.created",
  "timestamp": "ISO 8601 datetime",
  "data": {
    "bookmark_id": "uuid",
    "user_id": "string",
    "url": "string",
    "title": "string",
    "description": "string|null"
  },
  "metadata": {
    "service": "bookmark-service",
    "version": "1.0.0"
  }
}
```

**Downstream Consumers:**
- **Enrichment Service**: Fetches Open Graph metadata and updates bookmark
- **Validation Service** (planned): Validates URL accessibility

**Configuration:**
- Set `KAFKA_ENABLED=false` to disable event publishing (useful for testing)
- Events are compressed using gzip by default
- Failed publishes are retried up to 3 times

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
