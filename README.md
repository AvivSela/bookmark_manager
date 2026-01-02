# Bookmark Service

A microservices-based bookmark management application using Kafka and PostgreSQL.

## Prerequisites

- Docker Desktop or Docker Engine (20.10+)
- Docker Compose (2.0+)

## Quick Start

### 1. Environment Setup

Copy the example environment file and customize if needed:

```bash
cp .env.example .env
```

Edit [.env](.env) to change default passwords and ports.

### 2. Start Services

Start all services in detached mode:

```bash
docker compose up -d
```

Wait for services to be healthy (30-60 seconds):

```bash
docker compose ps
```

### 3. Access Services

Once running, you can access:

- **Bookmark Service API**: http://localhost:8000
  - REST API for bookmark CRUD operations
  - Interactive docs: http://localhost:8000/docs
  - Health check: http://localhost:8000/health

- **Enrichment Service**: http://localhost:8001
  - Kafka consumer for bookmark enrichment
  - Health check: http://localhost:8001/health

- **Validation Service**: http://localhost:8002
  - Validates bookmark URLs and metadata
  - Health check: http://localhost:8002/health

- **PostgreSQL Database**: `localhost:5432`
  - User: `bookmark_user` (configurable in [.env](.env))
  - Password: `bookmark_pass` (configurable in [.env](.env))
  - Database: `bookmark_db`

- **pgAdmin (PostgreSQL UI)**: http://localhost:5050
  - Email: `admin@example.com` (configurable in [.env](.env))
  - Password: `admin` (configurable in [.env](.env))

- **Kafka Broker**: `localhost:9092`
  - For application connections

- **Kafdrop (Kafka UI)**: http://localhost:9000
  - View topics, messages, and consumer groups

## Common Commands

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f kafka
docker compose logs -f postgres
```

### Stop Services

```bash
# Stop but keep data
docker compose down

# Stop and remove all data (clean slate)
docker compose down -v
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart kafka
```

### Check Service Status

```bash
docker compose ps
```

## Connecting to PostgreSQL

### Using psql

```bash
docker exec -it bookmark-postgres psql -U bookmark_user -d bookmark_db
```

### Using pgAdmin

1. Open http://localhost:5050
2. Login with credentials from [.env](.env)
3. The PostgreSQL server is **automatically configured** and appears as "Bookmark PostgreSQL" in the sidebar
   - Credentials are pre-configured (no manual setup needed)
   - Configuration is persisted in the `pgadmin_data` volume

**Manual server registration** (if needed):
- Right-click "Servers" → "Register" → "Server"
- General tab: Name = "Bookmark DB"
- Connection tab:
  - Host: `postgres` (service name)
  - Port: `5432`
  - Username: `bookmark_user`
  - Password: `bookmark_pass`
  - Save password: Yes

## Working with Kafka

### Using Kafka CLI Tools

```bash
# List topics
docker exec -it bookmark-kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Create a topic
docker exec -it bookmark-kafka kafka-topics.sh --bootstrap-server localhost:9092 --create --topic my-topic --partitions 3 --replication-factor 1

# Describe topic
docker exec -it bookmark-kafka kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic my-topic

# Produce messages
docker exec -it bookmark-kafka kafka-console-producer.sh --bootstrap-server localhost:9092 --topic my-topic

# Consume messages
docker exec -it bookmark-kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic my-topic --from-beginning
```

### Using Kafdrop UI

1. Open http://localhost:9000
2. Browse topics, view messages, and monitor consumer groups
3. No authentication required

## Architecture

### Services

- **Bookmark Service**: FastAPI REST API for bookmark CRUD operations with Kafka event publishing
- **Validation Service**: Kafka consumer that validates bookmark URLs and metadata, with retry mechanism
- **Enrichment Service**: Kafka consumer that enriches validated bookmarks with Open Graph metadata
- **PostgreSQL 16**: Primary database with Alpine Linux base
- **Kafka 3.x**: Message broker using KRaft mode (no Zookeeper)
- **Kafdrop**: Web UI for Kafka management
- **pgAdmin 4**: Web UI for PostgreSQL administration

### Service Communication

```
                        ┌──────────────────┐
                        │ Validation Svc   │
                        │   (Port 8002)    │
                        └────────┬─────────┘
                                 │
                                 │ HTTP PUT
                                 │ (update status)
                                 ▼
┌─────────────────┐         ┌───────────────┐         ┌──────────────────┐
│     Kafka       │<─────── │ Bookmark API  │<─────── │ Enrichment Svc   │
│ bookmark.created│         │  (Port 8000)  │         │   (Port 8001)    │
└────────┬────────┘         └───────┬───────┘         └──────────────────┘
         │                          │                           ▲
         │                          │                           │
         │                          │                   HTTP PUT (update metadata)
         └──────────────────────────┼───────────────────────────┘
                                    ▼
                            ┌───────────────┐
                            │  PostgreSQL   │
                            │  (Port 5432)  │
                            └───────────────┘
```

**Event Flow:**
1. User creates bookmark via Bookmark API
2. Bookmark saved to PostgreSQL with `pending_validation` status
3. `bookmarks.bookmark.created` event published to Kafka
4. **Validation Service** consumes `bookmark.created` event and validates:
   - URL accessibility and response codes
   - Content type validation
   - Security checks (redirects, HTTPS)
5. Validation Service calls Bookmark API (HTTP PUT) to update status:
   - Valid bookmarks → `validated` status
   - Invalid bookmarks → `validation_failed` status (with retry mechanism for transient failures)
6. **Enrichment Service** also consumes `bookmark.created` events independently
7. Enrichment Service fetches Open Graph metadata (runs in parallel with validation)
8. Enrichment Service calls Bookmark API (HTTP PUT) to update bookmark with metadata and sets status to `enriched`

**Error Handling:**
- Validation Service retries failed validations with exponential backoff
- Transient failures (network issues, timeouts) trigger automatic retries
- Permanent failures (invalid URLs, unsupported content) mark bookmarks as failed
- All status transitions are tracked in the database via Bookmark API calls

### Data Persistence

All data is stored in Docker named volumes:

- `postgres_data`: Database files
- `kafka_data`: Kafka logs and topics
- `pgadmin_data`: pgAdmin configuration and user preferences

Data persists across `docker compose down` but is removed with `docker compose down -v`.

### pgAdmin Server Configuration

The PostgreSQL server is automatically registered in pgAdmin using:
- [pgadmin/servers.json](pgadmin/servers.json): Server connection details
- [pgadmin/pgpass](pgadmin/pgpass): Stored password file (PostgreSQL password format)

These files are mounted into the pgAdmin container, so the server configuration persists and requires no manual setup.

### Networking

All services communicate via the `bookmark-network` bridge network. Services can reach each other using their container names:
- PostgreSQL: `bookmark-postgres:5432`
- Kafka: `bookmark-kafka:9092`
- pgAdmin: `bookmark-pgadmin:80`
- Kafdrop: `bookmark-kafdrop:9000`

**Note**: Applications running inside the Docker network should use `bookmark-kafka:9092` to connect to Kafka, not `localhost:9092`.

## Configuration

### Environment Variables

All configuration is in [.env](.env). See [.env.example](.env.example) for available options.

### Port Customization

Change ports in [.env](.env):

```env
POSTGRES_PORT=5432
KAFKA_PORT=9092
KAFDROP_PORT=9000
PGADMIN_PORT=5050
```

### Resource Limits

For production, consider adding resource limits to [docker-compose.yml](docker-compose.yml):

```yaml
services:
  kafka:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## Troubleshooting

### Services Won't Start

1. Check if ports are already in use:
   ```bash
   lsof -i :5432  # PostgreSQL
   lsof -i :9092  # Kafka
   ```

2. Check service logs:
   ```bash
   docker compose logs kafka
   ```

### Kafka Connection Issues

- Ensure Kafka is healthy: `docker compose ps kafka`
- Wait 30-60 seconds after startup for Kafka to be ready
- Check Kafka logs: `docker compose logs kafka`
- If Kafdrop can't connect: Ensure `KAFKA_ADVERTISED_LISTENERS` in [docker-compose.yml](docker-compose.yml) is set to `PLAINTEXT://bookmark-kafka:9092` (not `localhost`)

### PostgreSQL Connection Issues

- Verify credentials in [.env](.env) match your connection string
- Check PostgreSQL logs: `docker compose logs postgres`

### Reset Everything

To start fresh:

```bash
docker compose down -v
docker compose up -d
```

## Security Notes

- Default credentials are for **development only**
- Change all passwords in [.env](.env) for production
- Never commit [.env](.env) to version control (already in [.gitignore](.gitignore))
- Use Docker secrets or a secrets manager for production

## Service Documentation

- **Bookmark Service**: See [services/bookmark_service/README.md](services/bookmark_service/README.md)
- **Enrichment Service**: See [services/enrichment_service/README.md](services/enrichment_service/README.md)
- **Validation Service**: See [services/validation_service/](services/validation_service/)

## Next Steps

- Explore the interactive API documentation at http://localhost:8000/docs
- Monitor Kafka topics and messages in Kafdrop
- Use pgAdmin to view enriched bookmark data
- Add additional microservices following the existing patterns

## License

[Your License Here]
