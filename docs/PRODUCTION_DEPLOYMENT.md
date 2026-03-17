# Production Deployment Guide

Enterprise-ready deployment for European government use.

## Overview

The backend is designed for:
- **GDPR compliance** – audit logging, data handling
- **European government** – security headers, rate limiting, structured logging
- **Container deployment** – Docker, Kubernetes-ready health checks

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `JWT_SECRET` | Strong random secret for JWT signing (min 32 chars) |
| `ADMIN_SEED_EMAIL` | Email of the initial admin user seeded on first startup |
| `ADMIN_SEED_PASSWORD` | Password of the initial admin user seeded on first startup |

### Security (Production)

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins (restrict in prod) |
| `RATE_LIMIT_REQUESTS` | 60 | Requests per IP per minute |
| `TRUST_PROXY` | false | Set true behind load balancer |
| `AUDIT_LOG_ENABLED` | true | Enable audit logging |
| `AUDIT_LOG_PATH` | (stdout) | File path for audit log |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_FORMAT` | json | `json` for production, `text` for dev |
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING, ERROR |

## Docker Deployment

```bash
# Build
docker build -t ulss9-chatbot:latest .

# Run with env file
docker run -d \
  --name ulss9-chatbot \
  -p 8000:8000 \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e JWT_SECRET="$JWT_SECRET" \
  -e ADMIN_SEED_EMAIL="$ADMIN_SEED_EMAIL" \
  -e ADMIN_SEED_PASSWORD="$ADMIN_SEED_PASSWORD" \
  -e CORS_ORIGINS="https://your-domain.gov.it" \
  -e TRUST_PROXY=true \
  -v $(pwd)/data:/app/data \
  ulss9-chatbot:latest
```

## Docker Compose

```bash
cp .env.example .env
# Edit .env with production values
docker-compose up -d
```

## Health Checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness – process running |
| `GET /ready` | Readiness – Gemini configured, can serve traffic |

Use in Kubernetes:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## API Versioning

- **Canonical:** `/api/v1/` (auth, chat, admin)
- **Legacy:** `/api/` (backward compatibility)

## Audit Logging

Events logged (JSON lines):
- `auth` – login attempts (success/failure)
- `admin` – store/document create/delete/upload
- `data_access` – chat, domain list (optional)

Configure `AUDIT_LOG_PATH` for file output. Use log aggregation (ELK, Splunk) for retention and analysis.

## Security Checklist

- [ ] Set `JWT_SECRET` to strong random value
- [ ] Restrict `CORS_ORIGINS` to known domains
- [ ] Enable `TRUST_PROXY` behind reverse proxy
- [ ] Set `AUDIT_LOG_ENABLED=true`
- [ ] Use HTTPS (TLS termination at load balancer)
- [ ] Change initial admin password via the application after first deployment
