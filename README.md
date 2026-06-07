<div align="center">

```
███████╗ █████╗ ██████╗
╚══███╔╝██╔══██╗██╔══██╗
  ███╔╝ ███████║██████╔╝
 ███╔╝  ██╔══██║██╔═══╝
███████╗██║  ██║██║
╚══════╝╚═╝  ╚═╝╚═╝
```

**Production-grade social network backend. Django microservices. 10M+ DAU.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.0-092E20?style=flat-square&logo=django&logoColor=white)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-manifests-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

## What is ZAP?

ZAP is a **complete, production-hardened backend architecture** for a modern social network — designed from the ground up for scale, adversarial users, and real operational constraints. It is not a tutorial project. Every decision has a justification; every trade-off is documented.

The full implementation guide covers architecture, Django models, DRF serializers, Celery tasks, Docker, Kubernetes manifests, and a GitHub Actions CI/CD pipeline — from empty folder to deployed microservices.

**Target:** 10M+ DAU · Feed p99 < 800ms · 99.99% uptime · GDPR compliant

---

## Architecture

ZAP is a monorepo of seven independently deployable Django services behind a routing gateway.

```
CLIENT (iOS · Android · Web)
         │
         ▼
   ┌─────────────┐
   │ API GATEWAY │  ← rate limiting, trace injection, JWT forwarding
   └──────┬──────┘
          │
    ┌─────┼──────────────────────────────────┐
    ▼     ▼       ▼        ▼       ▼        ▼
  AUTH   FEED   GRAPH   MEDIA    MOD    NOTIF
  :8000  :8001  :8002   :8003   :8004   :8005
    │     │                               │
    │     └── Celery Workers ─────────────┘
    │          fanout · rescore · score_content · deliver
    │
    ▼
PostgreSQL (per-service DB) + Redis (cache · broker · channels)
                                    │
                              S3 + CDN (media)
```

---

## Services

| Service | Responsibility | Stack |
|---|---|---|
| **api-gateway** | Reverse proxy, rate limiting, trace IDs | Django + httpx |
| **auth-service** | Users, JWT, GDPR deletion | Django + SimpleJWT + Argon2 |
| **feed-service** | Posts, ranked home feed, engagement | Django + Celery |
| **graph-service** | Follows, blocks, follower counts | Django + PostgreSQL |
| **media-service** | Presigned S3 uploads, image processing, CDN | Django + boto3 + Pillow |
| **moderation-service** | Toxicity scoring, spam detection, human queue | Django + Detoxify + Celery |
| **notification-service** | Real-time WebSocket push, persistence | Django Channels + Daphne |

---

## Key Design Decisions

### Feed: Hybrid Push/Pull Fanout
Users with <10K followers use **push fanout** — posts are written to follower feed tables on creation. Users with >10K followers use **pull** — their content is fetched and merged at read time. The threshold is configurable. This avoids the pathological case where one celebrity post triggers 50M DB writes, while keeping feed reads fast for the common case.

### Ranking: Batch Inference, Not Real-Time
Feed scores are computed via a gravity-decay model (engagement signals + author affinity + recency) and written to `FeedItem.score`. A Celery Beat task re-scores every 15 minutes. The top-20 candidates are optionally re-ranked at read time. Real-time per-request model inference at 10M DAU is a compute budget problem; this approach costs ~2% of that.

```python
# Hacker News-style decay + engagement + personalization
score = (likes * 1.0 + comments * 2.5 + shares * 3.0 + 1) / (age_hours + 2) ** 1.8
score *= user_affinity   # graph proximity multiplier
score *= (1.0 - moderation_score)  # trust penalty
```

### Moderation: Three Tiers
1. **Rule-based** (regex, link density) — synchronous, <5ms, catches obvious spam
2. **ML scoring** (Detoxify `unbiased` model) — async Celery task, writes back to post
3. **Human queue** — scores in the 0.4–0.7 range, no automatic action taken

Auto-remove threshold: `0.85`. Shadow-ban threshold: `0.70`. Everything below `0.40` is clean.

### Auth: UUID PKs Everywhere
No sequential integer IDs. UUIDs on all primary keys prevent enumeration attacks. PII (email, name) lives exclusively in the auth service. Every other service stores only `user_id: UUID`.

### GDPR: Soft Delete → Async Hard Delete
Deletion is immediate for the user (email scrambled, account inaccessible) but hard-deletion of data cascades asynchronously via Redis pub/sub. Each service listens for `account_deletions` events and cleans its own data. Hard delete runs 30 days after soft delete — giving time to catch errors without holding PII indefinitely.

---

## Quickstart (Local with Docker Compose)

**Prerequisites:** Docker 24+, Docker Compose v2, an AWS account (for S3) or LocalStack.

```bash
# 1. Clone
git clone https://github.com/your-username/zap.git
cd zap

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY and JWT_SECRET_KEY

# 3. Start everything
docker-compose -f infrastructure/docker/docker-compose.yml up --build

# 4. Run migrations (first time only)
docker-compose exec auth-service python manage.py migrate
docker-compose exec feed-service python manage.py migrate
docker-compose exec graph-service python manage.py migrate
docker-compose exec media-service python manage.py migrate
docker-compose exec moderation-service python manage.py migrate
docker-compose exec notification-service python manage.py migrate

# 5. Create a superuser
docker-compose exec auth-service python manage.py createsuperuser
```

**Services will be available at:**
| Service | URL |
|---|---|
| API Gateway | http://localhost:8080 |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## API Quick Reference

```bash
# Register
POST http://localhost:8080/api/v1/auth/register/
{"email": "you@example.com", "username": "mehran", "password": "...", "password_confirm": "..."}

# Login → returns access + refresh tokens
POST http://localhost:8080/api/v1/auth/login/
{"email": "you@example.com", "password": "..."}

# Create a post
POST http://localhost:8080/api/v1/posts/
Authorization: Bearer <access_token>
{"content": "Hello, ZAP.", "media_urls": [], "hashtags": ["launch"]}

# Get home feed (cursor-paginated, ranked)
GET http://localhost:8080/api/v1/feed/home/
Authorization: Bearer <access_token>

# Follow a user
POST http://localhost:8080/api/v1/users/{user_id}/follow/

# Connect to notifications (WebSocket)
WS ws://localhost:8080/ws/notifications/?token=<access_token>

# Upload media (get presigned URL first, then PUT directly to S3)
POST http://localhost:8080/api/v1/media/presign/
{"mime_type": "image/jpeg", "file_size_bytes": 204800}
```

---

## Repository Structure

```
zap/
├── services/
│   ├── api-gateway/          # Routing proxy
│   ├── auth-service/         # Users, JWT, GDPR
│   ├── feed-service/         # Posts, ranking, engagement
│   ├── graph-service/        # Follows, blocks
│   ├── media-service/        # Uploads, processing, CDN
│   ├── moderation-service/   # Content safety
│   └── notification-service/ # WebSocket push
├── shared/
│   ├── base_settings.py      # Common Django config
│   ├── middleware/            # Logging, trace IDs
│   ├── pagination.py         # Cursor-only (no offset)
│   └── exceptions.py         # Standardized error format
├── infrastructure/
│   ├── docker/               # Dockerfile + Compose
│   └── k8s/                  # Deployments, HPA, Ingress
└── .github/
    └── workflows/
        └── ci.yml            # Test → Build → Deploy
```

---

## Production Checklist

Before you go live, verify each of these:

- [ ] `DEBUG=False` and `SECRET_KEY` is 50+ random characters
- [ ] `ALLOWED_HOSTS` locked to your actual domains
- [ ] CORS origins restricted to your frontend domains
- [ ] Postgres password rotated from the dev default
- [ ] Redis password set and `requirepass` enabled
- [ ] S3 bucket policy denies public `ListBucket`
- [ ] JWT `SECRET_KEY` is different from Django `SECRET_KEY`
- [ ] Rate limits tuned for your actual traffic profile
- [ ] `CELERY_TASK_ACKS_LATE=True` (re-queue on worker crash)
- [ ] Celery beat schedule running for `batch_rescore_feeds` and `cleanup_expired_tokens`
- [ ] Liveness and readiness probes responding on all pods
- [ ] Grafana dashboards and alerts configured for feed p99, error rate, queue depth
- [ ] GDPR deletion flow tested end-to-end before launch

---

## Performance Characteristics

| Metric | Target | Mechanism |
|---|---|---|
| Feed read p99 | < 800ms | Redis sorted-set cache + indexed FeedItem table |
| Post write | < 200ms | Async fanout; HTTP response before task completes |
| WebSocket delivery | < 100ms | Django Channels + Redis pub/sub |
| Moderation latency | < 5s (tier 2) | Celery async task; rule-based sync in <5ms |
| Uptime | 99.99% | HPA + rolling updates + circuit breakers + graceful degradation |

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Django 5 + DRF | Battle-tested ORM, admin, and ecosystem |
| Auth | SimpleJWT + Argon2 | OWASP-recommended hashing; stateless tokens |
| Task queue | Celery + Redis | Reliable async fanout and ML batch jobs |
| Database | PostgreSQL 16 | JSONB, partial indexes, advisory locks |
| Cache/Broker | Redis 7 | Sorted sets for feed ranking; pub/sub for events |
| WebSockets | Django Channels + Daphne | ASGI, integrates with existing Django auth |
| Media | S3 + CloudFront | Client-direct upload; global CDN edge |
| Containers | Docker + Kubernetes | HPA, rolling updates, pod disruption budgets |
| Observability | OpenTelemetry + Prometheus + Grafana + Loki | Full trace/metric/log coverage |
| CI/CD | GitHub Actions | Parallel per-service test → build → deploy |

---

## Contributing

```bash
# Branch naming
git checkout -b feature/your-feature    # new capability
git checkout -b fix/what-you-fixed      # bug fix
git checkout -b chore/what-you-did      # tooling, deps, config

# Commit format (Conventional Commits)
git commit -m "feat(feed): add explore feed endpoint with hashtag filtering"
git commit -m "fix(auth): handle token refresh race condition on concurrent requests"
git commit -m "chore(deps): bump Celery to 5.4.1"

# Merges always use --no-ff
git merge --no-ff feature/your-feature -m "feat: merge your-feature into develop"
```

PRs require: passing CI, ≥70% test coverage on changed files, and at least one review.

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
<sub>Built for engineers who will read the source code before trusting it.</sub>
</div>
