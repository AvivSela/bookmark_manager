# Validation Service

A Kafka consumer service that automatically validates bookmark URLs to ensure they are accessible and tracks their status over time. Supports both event-driven validation and periodic revalidation with configurable scheduling.

## Features

- **Kafka Event Consumption**: Listens to `bookmarks.bookmark.created` events
- **URL Validation**: Validates URLs using HTTP HEAD requests with GET fallback
- **Automatic Retry Logic**: Exponential backoff with configurable retry attempts
- **Redirect Handling**: Follows redirects (max 5 hops) and stores final URL
- **Periodic Revalidation**: Optional scheduler for revalidating stale bookmarks
- **Event Publishing**: Publishes validation results to `bookmarks.validation.completed` topic
- **Bookmark Service Integration**: Updates bookmarks via REST API (not direct DB access)
- **Health Check Endpoint**: FastAPI health check for monitoring
- **Manual Validation API**: REST endpoint for on-demand validation

## Tech Stack

- **Framework**: FastAPI 0.109.0
- **Message Broker**: Kafka (via aiokafka)
- **HTTP Client**: httpx (async)
- **Scheduler**: APScheduler 3.10.4
- **Retry Logic**: tenacity
- **Server**: Uvicorn
- **Testing**: pytest, pytest-asyncio, respx

## How It Works

### Architecture

```
┌─────────────────┐                    ┌──────────────────────────────────────┐
│  Bookmark API   │──── Kafka Event ───>│     Validation Service (8002)        │
│  (Port 8000)    │   bookmark.created │                                      │
└─────────────────┘                    │  ┌────────────────────────────────┐  │
                                       │  │  Bookmark Consumer             │  │
                                       │  └──────────┬─────────────────────┘  │
                                       │             │                        │
                                       │  ┌──────────▼─────────────────────┐  │
                                       │  │  URL Validator                 │  │
                                       │  │  (HEAD/GET with retry logic)   │  │
                                       │  └──────────┬─────────────────────┘  │
                                       │             │                        │
                                       │  ┌──────────▼─────────────────────┐  │
                                       │  │  Validation Event Producer     │  │
                                       │  │  (Publish to Kafka)            │  │
                                       │  └──────────┬─────────────────────┘  │
                                       │             │                        │
                                       │  ┌──────────▼─────────────────────┐  │
                                       │  │  Bookmark Service Client       │  │
                                       │  │  (PATCH /bookmarks/{id})       │  │
                                       │  └────────────────────────────────┘  │
                                       │                                      │
                                       │  ┌────────────────────────────────┐  │
                                       │  │  Revalidation Scheduler        │  │
                                       │  │  (Optional, runs periodically) │  │
                                       │  └────────────────────────────────┘  │
                                       └──────────────────────────────────────┘
```

### Event Flow

1. **Bookmark Created**: User creates a bookmark via Bookmark API
2. **Event Published**: Bookmark service publishes `bookmarks.bookmark.created` event to Kafka
3. **Event Consumed**: Validation service receives the event with bookmark URL and ID
4. **URL Validation**:
   - Makes HTTP HEAD request to check URL accessibility
   - Falls back to GET if HEAD returns 405 (Method Not Allowed)
   - Follows redirects (max 5 hops) and stores final URL
   - Accepts 2xx status codes as valid
5. **Result Publishing**: Publishes validation result to `bookmarks.validation.completed` topic
6. **Bookmark Update**: Sends PATCH request to Bookmark Service REST API with validation status
7. **Retry on Failure**: Exponential backoff retry for transient failures (network errors, timeouts)
8. **Periodic Revalidation** (optional): Scheduler periodically checks stale bookmarks and revalidates them

## Configuration

Configuration is managed through environment variables defined in [app/config.py](app/config.py):

| Variable | Description | Default |
| -------- | ----------- | ------- |
| **Application** | | |
| `APP_NAME` | Service name | `Bookmark Validation Service` |
| `APP_VERSION` | Service version | `1.0.0` |
| `HOST` | API server host | `0.0.0.0` |
| `PORT` | API server port | `8002` |
| `DEBUG` | Debug mode | `false` |
| **Kafka** | | |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `bookmark-kafka:9092` |
| `KAFKA_TOPIC` | Topic to consume | `bookmarks.bookmark.created` |
| `KAFKA_CONSUMER_GROUP` | Consumer group ID | `validation-service` |
| `KAFKA_VALIDATION_TOPIC` | Validation result topic | `bookmarks.validation.completed` |
| `KAFKA_AUTO_OFFSET_RESET` | Offset reset strategy | `earliest` |
| `KAFKA_SESSION_TIMEOUT_MS` | Session timeout | `30000` |
| `KAFKA_MAX_POLL_RECORDS` | Max records per poll | `10` |
| **Validation** | | |
| `VALIDATION_TIMEOUT_SECONDS` | HTTP request timeout | `10` |
| `VALIDATION_MAX_ATTEMPTS` | Max retry attempts | `3` |
| `VALIDATION_INITIAL_RETRY_DELAY` | Initial retry delay (seconds) | `1.0` |
| `VALIDATION_MAX_RETRY_DELAY` | Max retry delay (seconds) | `10.0` |
| `VALIDATION_BACKOFF_MULTIPLIER` | Backoff multiplier | `2.0` |
| `VALIDATION_USER_AGENT` | HTTP User-Agent header | `BookmarkValidator/1.0` |
| **Scheduler** | | |
| `ENABLE_SCHEDULER` | Enable internal scheduler | `true` |
| `REVALIDATION_INTERVAL_HOURS` | Revalidation interval | `24` |
| `REVALIDATION_BATCH_SIZE` | Batch size for revalidation | `100` |
| `REVALIDATION_STALE_THRESHOLD_DAYS` | Days before bookmark is stale | `7` |
| **Bookmark Service** | | |
| `BOOKMARK_SERVICE_HOST` | Bookmark service host | `bookmark-service` |
| `BOOKMARK_SERVICE_PORT` | Bookmark service port | `8000` |
| `BOOKMARK_SERVICE_TIMEOUT_SECONDS` | API request timeout | `10` |

## Quick Start

### Running with Docker Compose

From the project root:

```bash
docker compose up validation-service
```

The service will:
- Start consuming Kafka events automatically
- Expose health check at `http://localhost:8002/health`
- Expose validation API at `http://localhost:8002/validation`

### Running Locally (Development)

1. **Set up Python environment**:

```bash
cd services/validation_service

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
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_TOPIC=bookmarks.bookmark.created
export BOOKMARK_SERVICE_HOST=localhost
export BOOKMARK_SERVICE_PORT=8000
```

3. **Ensure dependencies are running**:

```bash
# Start Kafka and Bookmark Service
docker compose up kafka bookmark-service -d
```

4. **Run the service**:

```bash
python -m app.main
```

The service will start both:
- Kafka consumer (background)
- FastAPI API endpoint at `http://localhost:8002`

## Validation Data

The service validates URLs and stores the following metadata:

### ValidationResult Schema

- **bookmark_id**: UUID of the bookmark
- **url**: Original URL
- **is_valid**: Boolean indicating if URL is accessible
- **http_status**: HTTP status code (200, 404, etc.)
- **final_url**: Final URL after redirects (if different from original)
- **error_message**: Error message if validation failed
- **validated_at**: Timestamp of validation
- **redirect_chain**: List of URLs in redirect chain (if any)

### Validation Logic

1. **HEAD Request First**: Uses lightweight HEAD request (no body download)
2. **GET Fallback**: Falls back to GET if HEAD returns 405
3. **Redirect Following**: Follows up to 5 redirects, stores final URL
4. **Success Criteria**: 2xx status codes considered valid
5. **Error Handling**: Network errors, timeouts, and DNS failures handled gracefully

## Testing

The test suite uses pytest with async support.

### Run all tests

```bash
./run_tests.sh
```

### Run specific test files

```bash
# Test URL validator
.venv/bin/pytest tests/test_url_validator.py -v

# Test bookmark consumer
.venv/bin/pytest tests/test_bookmark_consumer.py -v

# Test validation routes
.venv/bin/pytest tests/test_validation.py -v
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
  "service": "validation-service",
  "version": "1.0.0",
  "kafka_connected": true
}
```

### Service Info

```bash
GET /
```

Returns basic service information.

### Manual Validation

```bash
POST /validation
Content-Type: application/json

{
  "bookmark_id": "123e4567-e89b-12d3-a456-426614174000",
  "url": "https://example.com"
}
```

**Response:**
```json
{
  "bookmark_id": "123e4567-e89b-12d3-a456-426614174000",
  "url": "https://example.com",
  "is_valid": true,
  "http_status": 200,
  "final_url": "https://example.com",
  "validated_at": "2025-01-02T10:30:00Z"
}
```

## Periodic Revalidation

The service includes an optional scheduler for periodic revalidation of bookmarks:

### How It Works

1. **Scheduler Runs**: Every `REVALIDATION_INTERVAL_HOURS` (default: 24 hours)
2. **Fetch Stale Bookmarks**: Queries Bookmark Service for bookmarks older than `REVALIDATION_STALE_THRESHOLD_DAYS`
3. **Batch Processing**: Revalidates in batches of `REVALIDATION_BATCH_SIZE`
4. **Event Publishing**: Publishes validation results to Kafka for downstream processing

### Disabling the Scheduler

Set `ENABLE_SCHEDULER=false` if you want to use an external scheduler (e.g., cron, Kubernetes CronJob):

```bash
export ENABLE_SCHEDULER=false
```

## Retry Strategy

The service uses exponential backoff for retrying failed validations:

- **Max Attempts**: 3 (configurable via `VALIDATION_MAX_ATTEMPTS`)
- **Initial Delay**: 1 second (configurable via `VALIDATION_INITIAL_RETRY_DELAY`)
- **Max Delay**: 10 seconds (configurable via `VALIDATION_MAX_RETRY_DELAY`)
- **Backoff Multiplier**: 2.0 (doubles delay each retry)

### Retry Logic

1. First attempt: Immediate
2. Second attempt: After 1 second
3. Third attempt: After 2 seconds
4. Failure: Mark as invalid, publish error

## Error Handling

The service handles various error scenarios:

- **Network Errors**: Connection refused, DNS failures, timeouts
- **HTTP Errors**: 4xx and 5xx status codes
- **Redirect Errors**: Infinite redirects, too many redirects
- **Timeout Errors**: Request exceeds timeout threshold
- **Invalid URLs**: Malformed URLs, unsupported schemes

All errors are logged and published to Kafka for monitoring and alerting.
