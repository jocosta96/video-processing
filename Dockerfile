# Stage 1: Build
FROM python:3.11.12-alpine3.21 AS builder

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt \
    && pip freeze > /code/requirements.lock

# Stage 2: Runtime
FROM python:3.11.12-alpine3.21

# Create non-root user
RUN addgroup -g 1000 appuser && adduser -D -u 1000 -G appuser appuser

WORKDIR /code

COPY --from=builder /code/requirements.lock /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy configuration files
#COPY ./alembic.ini /code/alembic.ini

# Copy the Clean Architecture source code
COPY ./src /code/src

# Copy the webhook directory
#COPY ./webhook /code/webhook

# Copy the infra scripts directory
#COPY ./infra/scripts /code/infra/scripts

# Set proper permissions for appuser
RUN chown -R appuser:appuser /code

# Set environment variables for Clean Architecture
ENV PYTHONPATH=/code
ENV PYTHONUNBUFFERED=1

USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1
