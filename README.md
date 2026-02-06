# FIAP X - Video Processing System

Sistema de processamento de videos para extracao de frames, implementado como microsservicos.

## Arquitetura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  fiapx-api  │────▶│fiapx-worker │────▶│fiapx-notifier│
│  (FastAPI)  │     │  (Python)   │     │   (Python)  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────┐
│                    RabbitMQ                         │
└─────────────────────────────────────────────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌───────────┐     ┌───────────┐     ┌───────────┐
│ PostgreSQL│     │   MinIO   │     │   Redis   │
└───────────┘     └───────────┘     └───────────┘
```

## Projetos

| Projeto | Descricao | Porta |
|---------|-----------|-------|
| [fiapx-api](./fiapx-api) | API Gateway - autenticacao, upload, status | 8000 |
| [fiapx-worker](./fiapx-worker) | Worker - processamento de video com FFmpeg | - |
| [fiapx-notifier](./fiapx-notifier) | Notificador - envio de emails | - |
| [infra](./infra) | Docker Compose e configuracoes | - |

## Quick Start

```bash
cd infra
./scripts/setup.sh
```

## Endpoints da API

```
POST /api/v1/auth/register  - Cadastro
POST /api/v1/auth/login     - Login
POST /api/v1/videos/upload  - Upload de video
GET  /api/v1/videos         - Listar videos
GET  /api/v1/videos/{id}    - Detalhes do video
GET  /api/v1/jobs/{id}/download - URL de download
```

## Servicos

| Servico | URL | Credenciais |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | - |
| RabbitMQ | http://localhost:15672 | guest/guest |
| MinIO | http://localhost:9001 | minioadmin/minioadmin |
| Grafana | http://localhost:3000 | admin/admin |
| Mailhog | http://localhost:8025 | - |

## Comunicacao entre Servicos

```
API ──publish──▶ video.process ──consume──▶ Worker
                                              │
Worker ──publish──▶ notification.send ──consume──▶ Notifier
```

## Stack

- **API**: FastAPI, SQLAlchemy, Pydantic
- **Worker**: Python, FFmpeg, pika
- **Notifier**: Python, SMTP, pika
- **Broker**: RabbitMQ
- **Database**: PostgreSQL
- **Cache/Lock**: Redis
- **Storage**: MinIO (S3)
