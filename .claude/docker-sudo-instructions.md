# Docker Command Instructions for Claude Code

## Environment Context
- User: aviv
- Project: bookmark
- Docker requires sudo privileges in this environment

## Docker Command Guidelines

### Always Use Sudo for Docker Commands
All Docker and Docker Compose commands MUST be prefixed with `sudo`:

**Correct:**
```bash
sudo docker compose ps
sudo docker compose up -d
sudo docker compose down
sudo docker ps
sudo docker logs <container>
sudo docker exec -it <container> bash
```

**Incorrect:**
```bash
docker compose ps
docker ps
```

### Auto-Approved Commands
The following sudo Docker commands are auto-approved in settings:
- `sudo docker compose:*` (all docker compose commands)
- `sudo docker exec:*` (all docker exec commands)

### Running Services
Current services in docker-compose.yml:
- postgres (port 5432)
- pgadmin (port 5050)
- kafka (ports 9092-9093)
- kafdrop (port 9000)

### Common Operations

**Check running containers:**
```bash
sudo docker compose ps
```

**View logs:**
```bash
sudo docker compose logs <service-name>
sudo docker compose logs -f <service-name>  # follow logs
```

**Start services:**
```bash
sudo docker compose up -d
```

**Stop services:**
```bash
sudo docker compose down
```

**Execute commands in containers:**
```bash
sudo docker exec -it bookmark-postgres psql -U user -d bookmarkdb
sudo docker exec -it bookmark-postgres bash
```

**Restart a service:**
```bash
sudo docker compose restart <service-name>
```

## Important Notes
- User has not added their user to the docker group
- All Docker commands will fail without sudo
- The sudo commands are pre-approved and won't require user confirmation
