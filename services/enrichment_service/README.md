# Enrichment Service

A Kafka consumer service that automatically enriches bookmarks with metadata based on resource type detection. Supports web pages, images, datasets, APIs, and more through a pluggable enricher architecture.

## Features

- **Kafka Event Consumption**: Listens to `bookmarks.bookmark.created` events
- **Resource Type Detection**: Automatically detects resource type (webpage, image, dataset, API, etc.) using URL patterns, file extensions, and content-type headers
- **Pluggable Enricher Architecture**: Modular enrichers for different resource types
- **Parallel Enrichment**: Runs multiple enrichers concurrently for maximum performance
- **Specialized Enrichers**:
  - **WebPage**: Open Graph metadata, meta tags, favicon extraction
  - **Image**: Dimensions, format, file size (using minimal bandwidth)
  - **Dataset**: Format detection, row/column counts, schema inference
  - **API**: OpenAPI/Swagger spec detection, endpoint discovery
- **Bookmark Service Integration**: Updates bookmarks via REST API (not direct DB access)
- **Health Check Endpoint**: FastAPI health check for monitoring
- **Retry Logic**: Exponential backoff with configurable retry attempts
- **Concurrent Processing**: Asynchronous event processing with configurable parallelism

## Tech Stack

- **Framework**: FastAPI 0.109.0 (for health endpoint)
- **Message Broker**: Kafka (via aiokafka)
- **HTTP Client**: httpx (async)
- **HTML Parser**: BeautifulSoup4
- **Image Processing**: Pillow (PIL)
- **CSV/Data Parsing**: csv, json, xml.etree
- **Retry Logic**: tenacity
- **Server**: Uvicorn
- **Testing**: pytest, pytest-asyncio, pytest-mock


## How It Works

### Architecture

```
┌─────────────────┐                    ┌──────────────────────────────────────┐
│  Bookmark API   │──── Kafka Event ───>│     Enrichment Service (8001)        │
│  (Port 8000)    │   bookmark.created │                                      │
└─────────────────┘                    │  ┌────────────────────────────────┐  │
                                       │  │  Bookmark Consumer             │  │
                                       │  └──────────┬─────────────────────┘  │
                                       │             │                        │
                                       │  ┌──────────▼─────────────────────┐  │
                                       │  │  Resource Type Detector        │  │
                                       │  │  (URL pattern, content-type)   │  │
                                       │  └──────────┬─────────────────────┘  │
                                       │             │                        │
                                       │  ┌──────────▼─────────────────────┐  │
                                       │  │  Enrichment Orchestrator       │  │
                                       │  │  (Parallel enricher execution) │  │
                                       │  └──────────┬─────────────────────┘  │
                                       │             │                        │
                                       │  ┌──────────▼─────────────────────┐  │
                                       │  │  Enrichers (run in parallel):  │  │
                                       │  │  • WebPageEnricher             │  │
                                       │  │  • ImageEnricher               │  │
                                       │  │  • DatasetEnricher             │  │
                                       │  │  • ApiEnricher                 │  │
                                       │  └──────────┬─────────────────────┘  │
                                       │             │                        │
                                       │  ┌──────────▼─────────────────────┐  │
                                       │  │  Bookmark Service Client       │  │
                                       │  │  (PATCH /bookmarks/{id})       │  │
                                       │  └────────────────────────────────┘  │
                                       └──────────────┬───────────────────────┘
                                                      │
                                          ┌───────────▼────────────┐
                                          │   Bookmark Service     │
                                          │   (Updates DB)         │
                                          └────────────────────────┘
```

### Event Flow

1. **Bookmark Created**: User creates a bookmark via Bookmark API
2. **Event Published**: Bookmark service publishes `bookmarks.bookmark.created` event to Kafka
3. **Event Consumed**: Enrichment service receives the event with bookmark URL and ID
4. **Resource Type Detection**:
   - Analyzes URL patterns (e.g., `/api/`, `.jpg`, `.csv`)
   - Makes HEAD request to check `Content-Type` header
   - Determines primary resource type (webpage, image, dataset, api, etc.)
5. **Enricher Selection**: Orchestrator selects applicable enrichers based on resource type
6. **Parallel Enrichment**: Runs multiple enrichers concurrently:
   - **WebPageEnricher**: Fetches HTML, extracts Open Graph tags, meta tags, favicon
   - **ImageEnricher**: Extracts dimensions, format, file size (minimal bandwidth)
   - **DatasetEnricher**: Detects format, counts rows/columns, infers schema
   - **ApiEnricher**: Finds OpenAPI/Swagger spec, extracts endpoint info
7. **Result Merging**: Combines data from all enrichers into single `EnrichmentResult`
8. **Bookmark Update**: Sends PATCH request to Bookmark Service REST API
9. **Retry on Failure**: Exponential backoff retry for transient failures (network errors, timeouts)

## Configuration

Configuration is managed through environment variables defined in [app/config.py](app/config.py):

| Variable | Description | Default |
| -------- | ----------- | ------- |
| **Application** | | |
| `APP_NAME` | Service name | `Bookmark Enrichment Service` |
| `APP_VERSION` | Service version | `1.0.0` |
| `HOST` | API server host | `0.0.0.0` |
| `PORT` | API server port | `8001` |
| `DEBUG` | Debug mode | `false` |
| **Kafka** | | |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `bookmark-kafka:9092` |
| `KAFKA_TOPIC` | Topic to consume | `bookmarks.bookmark.created` |
| `KAFKA_CONSUMER_GROUP` | Consumer group ID | `enrichment-service` |
| `KAFKA_AUTO_OFFSET_RESET` | Offset reset strategy | `earliest` |
| `KAFKA_SESSION_TIMEOUT_MS` | Session timeout | `30000` |
| `KAFKA_MAX_POLL_RECORDS` | Max records per poll | `10` |
| **Bookmark Service** | | |
| `BOOKMARK_SERVICE_HOST` | Bookmark service host | `bookmark-service` |
| `BOOKMARK_SERVICE_PORT` | Bookmark service port | `8000` |
| `BOOKMARK_SERVICE_TIMEOUT_SECONDS` | API request timeout | `10` |
| **Enrichment** | | |
| `ENABLED_ENRICHERS` | Comma-separated enricher list | `webpage,image,dataset,api` |
| `MAX_PARALLEL_ENRICHERS` | Max concurrent enrichers | `5` |
| `ENRICHMENT_TIMEOUT_SECONDS` | Per-enricher timeout | `10` |
| `ENRICHMENT_MAX_ATTEMPTS` | Max retry attempts | `5` |
| `ENRICHMENT_INITIAL_RETRY_DELAY` | Initial retry delay (seconds) | `1.0` |
| `ENRICHMENT_MAX_RETRY_DELAY` | Max retry delay (seconds) | `60.0` |
| `ENRICHMENT_BACKOFF_MULTIPLIER` | Backoff multiplier | `2.0` |
| `USER_AGENT` | HTTP User-Agent header | `BookmarkEnricher/1.0` |
| **Image Enricher** | | |
| `IMAGE_MAX_HEADER_SIZE` | Max bytes to fetch for headers | `32768` (32KB) |
| `IMAGE_TIMEOUT_SECONDS` | Image fetch timeout | `10.0` |
| **Dataset Enricher** | | |
| `DATASET_ENABLE_PLATFORM_SCRAPING` | Enable platform-specific scraping | `true` |
| `DATASET_TIMEOUT_SECONDS` | Dataset fetch timeout | `15.0` |
| `DATASET_MAX_PAGE_SIZE` | Max page size in bytes | `5242880` (5MB) |
| **API Enricher** | | |
| `API_SPEC_PATHS` | Comma-separated spec paths | `/openapi.json,/swagger.json,/api-docs` |
| `API_ENABLE_HTML_FALLBACK` | Enable HTML fallback | `true` |
| `API_TIMEOUT_SECONDS` | API fetch timeout | `10.0` |

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

The service extracts and stores metadata that varies by resource type:

### Common Fields (All Resources)

- **resource_type**: Detected type (`webpage`, `image`, `dataset`, `api`, etc.)
- **favicon_url**: Extracted from `<link rel="icon">` or defaults to `/favicon.ico`

### WebPage Enricher

Extracts from HTML pages:

- **og_title**: Open Graph title
- **og_description**: Open Graph description
- **og_image**: Open Graph image URL
- **og_type**: Open Graph type (article, website, etc.)
- **og_site_name**: Site name
- **meta_description**: Standard meta description (fallback)

### Image Enricher

Extracts from image files (.jpg, .png, .gif, .webp, etc.):

- **media_metadata**:
  - `type`: "image"
  - `content_type`: MIME type (e.g., "image/jpeg")
  - `file_size_bytes`: File size
  - `width`: Image width in pixels
  - `height`: Image height in pixels
  - `format`: Image format (JPEG, PNG, etc.)

### Dataset Enricher

Extracts from data files (.csv, .json, .xml, etc.):

- **dataset_metadata**:
  - `format`: File format (csv, json, xml)
  - `row_count`: Number of rows (CSV)
  - `column_count`: Number of columns (CSV)
  - `columns`: List of column names
  - `sample_data`: First few rows
  - `schema`: Inferred data types
  - `file_size_bytes`: File size

### API Enricher

Extracts from API endpoints:

- **api_metadata**:
  - `api_spec_url`: URL to OpenAPI/Swagger spec
  - `api_title`: API title from spec
  - `api_version`: API version
  - `api_description`: API description
  - `endpoint_count`: Number of endpoints
  - `base_url`: API base URL

## Testing

The test suite uses pytest with async support.

### Run all tests

```bash
./run_tests.sh
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

## Resource Type Detection

The service automatically detects resource types using multiple signals:

### Detection Methods (in order of priority)

1. **URL Pattern Analysis**:
   - File extensions: `.jpg`, `.csv`, `.json`, `/api/`, etc.
   - Path patterns: `/api/v1/`, `/datasets/`, `/images/`
   - Domain patterns: `api.example.com`, `data.example.com`

2. **Content-Type Header** (HEAD request):
   - `image/*` → Image
   - `text/csv`, `application/json` → Dataset
   - `application/json` with `/api/` path → API
   - `text/html` → WebPage

3. **OpenGraph Type** (for webpages):
   - `og:type=article` → WebPage
   - `og:type=video` → Video

### Supported Resource Types

- `webpage`: HTML pages, articles, blogs
- `image`: JPEG, PNG, GIF, WebP, SVG
- `dataset`: CSV, JSON, XML, Parquet
- `api`: REST APIs, OpenAPI/Swagger endpoints
- `video`: MP4, WebM, YouTube, Vimeo (future)
- `audio`: MP3, WAV, podcasts (future)
- `pdf`: PDF documents (future)
- `code`: GitHub repos, source files (future)
- `unknown`: Fallback (uses webpage enricher)