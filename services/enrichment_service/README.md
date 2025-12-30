# Enrichment Service

A Kafka consumer service that automatically enriches bookmarks with Open Graph metadata, favicon URLs, and other metadata from the target websites.

## Features

- **Kafka Event Consumption**: Listens to `bookmarks.bookmark.created` events
- **Open Graph Metadata Extraction**: Fetches og:title, og:description, og:image, og:type, og:site_name
- **Favicon Detection**: Extracts favicon URLs from websites
- **Meta Tag Fallback**: Uses standard meta description if Open Graph tags aren't available
- **Automatic Updates**: Updates bookmarks via direct database access
- **Health Check Endpoint**: FastAPI health check for monitoring
- **Retry Logic**: Automatic retries for transient failures
- **Concurrent Processing**: Processes events asynchronously for high throughput

## Tech Stack

- **Framework**: FastAPI 0.109.0 (for health endpoint)
- **Message Broker**: Kafka (via aiokafka)
- **HTTP Client**: httpx (async)
- **HTML Parser**: BeautifulSoup4
- **Database**: PostgreSQL (via SQLAlchemy async)
- **Server**: Uvicorn
- **Testing**: pytest, pytest-asyncio

## Project Structure

```
enrichment_service/
├── app/
│   ├── __init__.py
│   ├── main.py                      # Service orchestrator (consumer + API)
│   ├── api.py                       # FastAPI app with health check
│   ├── config.py                    # Pydantic settings
│   ├── database.py                  # Database session management
│   ├── models/
│   │   ├── __init__.py
│   │   └── bookmark.py              # SQLAlchemy bookmark model
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── kafka_events.py          # Kafka event schemas
│   ├── consumers/
│   │   ├── __init__.py
│   │   └── bookmark_consumer.py     # Kafka consumer
│   ├── enrichers/
│   │   ├── __init__.py
│   │   ├── metadata_enricher.py     # Open Graph & metadata extraction
│   │   └── retry_handler.py         # Retry logic with tenacity
│   └── routes/
│       ├── __init__.py
│       └── health.py                # Health check endpoint
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Test fixtures
│   └── test_metadata_enricher.py   # Unit tests
├── .env.test                        # Test environment variables
├── requirements.txt                 # Python dependencies
├── pytest.ini                      # Pytest configuration
├── run_tests.sh                    # Test runner script
└── Dockerfile                      # Multi-stage production Docker build
```

## How It Works

### Architecture

```
┌─────────────────┐                    ┌──────────────────┐
│  Bookmark API   │──── Kafka Event ───>│ Enrichment Svc   │
│  (Port 8000)    │   bookmark.created │  (Port 8001)     │
└─────────────────┘                    └────────┬─────────┘
                                                │
                                                │ 1. Consume event
                                                │ 2. Fetch URL
                                                │ 3. Parse HTML
                                                │ 4. Extract metadata
                                                │ 5. Update DB
                                                │
                                         ┌──────▼───────┐
                                         │  PostgreSQL  │
                                         │  (Port 5432) │
                                         └──────────────┘
```

### Event Flow

1. **Bookmark Created**: User creates a bookmark via Bookmark API
2. **Event Published**: Bookmark service publishes `bookmarks.bookmark.created` event to Kafka
3. **Event Consumed**: Enrichment service receives the event
4. **URL Fetched**: Service makes HTTP GET request to bookmark URL
5. **Metadata Extracted**: Parses HTML for Open Graph tags, meta tags, and favicon
6. **Database Updated**: Updates bookmark record with enrichment data
7. **Retry on Failure**: Automatically retries on transient failures (network errors, timeouts)

## Configuration

Configuration is managed through environment variables defined in [app/config.py](app/config.py):

| Variable | Description | Default |
|----------|-------------|---------|
| **Application** | | |
| `APP_NAME` | Service name | `Bookmark Enrichment Service` |
| `APP_VERSION` | Service version | `1.0.0` |
| `HOST` | API server host | `0.0.0.0` |
| `PORT` | API server port | `8001` |
| `DEBUG` | Debug mode | `false` |
| **Database** | | |
| `POSTGRES_USER` | Database username | Required |
| `POSTGRES_PASSWORD` | Database password | Required |
| `POSTGRES_DB` | Database name | Required |
| `POSTGRES_HOST` | Database host | `postgres` |
| `POSTGRES_PORT` | Database port | `5432` |
| **Kafka** | | |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `bookmark-kafka:9092` |
| `KAFKA_TOPIC` | Topic to consume | `bookmarks.bookmark.created` |
| `KAFKA_CONSUMER_GROUP` | Consumer group ID | `enrichment-service` |
| **Enrichment** | | |
| `HTTP_TIMEOUT_SECONDS` | HTTP request timeout | `10` |
| `MAX_RETRIES` | Max retry attempts | `3` |
| `USER_AGENT` | HTTP User-Agent header | `BookmarkEnricher/1.0` |

## Quick Start

### Running with Docker Compose

From the project root:

```bash
docker compose up enrichment-service
```

The service will:
- Start consuming Kafka events automatically
- Expose health check at `http://localhost:8001/health`

### Running Locally (Development)

1. **Set up Python environment**:

```bash
cd services/enrichment_service

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
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_TOPIC=bookmarks.bookmark.created
```

3. **Ensure dependencies are running**:

```bash
# Start PostgreSQL and Kafka
docker compose up postgres kafka -d
```

4. **Run the service**:

```bash
python -m app.main
```

The service will start both:
- Kafka consumer (background)
- FastAPI health endpoint at `http://localhost:8001`

## Enrichment Data

The service extracts and stores the following metadata:

### Open Graph Protocol Tags

- **og_title**: `<meta property="og:title" content="...">`
- **og_description**: `<meta property="og:description" content="...">`
- **og_image**: `<meta property="og:image" content="...">`
- **og_type**: `<meta property="og:type" content="...">`
- **og_site_name**: `<meta property="og:site_name" content="...">`

### Standard Meta Tags (Fallback)

- **meta_description**: `<meta name="description" content="...">` (used if og:description not available)

### Favicon

- **favicon_url**: Extracted from `<link rel="icon">` or `<link rel="shortcut icon">` or defaults to `/favicon.ico`

## Testing

The test suite uses pytest with async support.

### Run all tests

```bash
./run_tests.sh
```

### Run specific test file

```bash
./run_tests.sh tests/test_metadata_enricher.py
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

## API Endpoints

### Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "enrichment-service",
  "version": "1.0.0",
  "kafka_connected": true,
  "database_connected": true
}
```

### Service Info

```bash
GET /
```

Returns basic service information.

## Development

### Code Quality

The codebase follows these principles:
- Type hints for all functions
- Comprehensive docstrings
- Async/await for I/O operations
- Proper error handling and retry logic
- Separation of concerns (consumer, enricher, database)

### Adding New Enrichers

1. Create enricher class in [app/enrichers/](app/enrichers/)
2. Implement extraction logic
3. Update [app/consumers/bookmark_consumer.py](app/consumers/bookmark_consumer.py) to use the enricher
4. Add tests in `tests/`
5. Update this README

### Retry Logic

The service uses the `tenacity` library for retry handling:

- **Max attempts**: 3 (for HTTP requests)
- **Backoff**: Exponential (1s → 2s → 4s)
- **Retry on**: Network errors, timeouts, HTTP 5xx
- **No retry on**: HTTP 4xx (client errors like 404)

## Troubleshooting

### Service won't start

Check that Kafka and PostgreSQL are running:

```bash
docker compose ps kafka postgres
```

### Not consuming events

1. Verify Kafka topic exists:
   ```bash
   docker exec -it bookmark-kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
   ```

2. Check consumer group status:
   ```bash
   docker compose logs enrichment-service
   ```

3. Verify bookmark service is publishing events (create a bookmark)

### Enrichment not working

1. Check service logs:
   ```bash
   docker compose logs -f enrichment-service
   ```

2. Verify the target URL is accessible
3. Check if the website has Open Graph tags (use browser dev tools)

### Database connection errors

Ensure PostgreSQL is running and credentials match:

```bash
docker compose logs postgres
docker compose ps postgres
```

## Monitoring

### View Logs

```bash
# Real-time logs
docker compose logs -f enrichment-service

# Last 100 lines
docker compose logs --tail=100 enrichment-service
```

### Check Consumer Health

```bash
curl http://localhost:8001/health
```

### Monitor Kafka Topics

Use Kafdrop UI at http://localhost:9000 to:
- View `bookmarks.bookmark.created` topic
- Check consumer group lag
- Inspect event payloads

## Performance

- **Concurrency**: Processes events asynchronously
- **Timeouts**: 10-second timeout for HTTP requests
- **Retries**: Automatic retry with exponential backoff
- **Resource Usage**: Lightweight, ~50-100MB memory under normal load

## Security Notes

- Uses read-only User-Agent header for HTTP requests
- Respects HTTP timeouts to prevent hanging
- Database credentials managed via environment variables
- No sensitive data logged in production mode

## Future Enhancements

- Content-type validation (only process HTML pages)
- Screenshot capture for visual previews
- Readability score calculation
- Language detection
- Keywords extraction
- Archive.org snapshot URLs
- Rate limiting per domain
- Webhook notifications on completion

## License

This project is part of the bookmark management system.
