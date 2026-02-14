#!/bin/bash
set -e

echo "=== FIAP X Setup ==="

cd "$(dirname "$0")/.."

# Generate JWT secret if not set
if [ -z "$JWT_SECRET" ]; then
    export JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "Generated JWT_SECRET"
fi

# Start all services
echo "Starting services..."
docker-compose up -d

# Wait for services
echo "Waiting for services..."
sleep 15

# Run migrations
echo "Running migrations..."
docker-compose exec -T api alembic upgrade head || echo "Run migrations manually if needed"

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Services:"
echo "  - API:        http://localhost:8000/docs"
echo "  - RabbitMQ:   http://localhost:15672 (guest/guest)"
echo "  - MinIO:      http://localhost:9001 (minioadmin/minioadmin)"
echo "  - Grafana:    http://localhost:3000 (admin/admin)"
echo "  - Mailhog:    http://localhost:8025"
echo ""
