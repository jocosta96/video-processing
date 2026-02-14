# FIAP X - Makefile for Development and Testing
#
# Usage:
#   make help          - Show available commands
#   make venv          - Create virtual environments
#   make install       - Install all dependencies
#   make test-unit     - Run unit tests
#   make test-int      - Run integration tests
#   make test-e2e      - Run E2E tests
#   make test-all      - Run all tests

.PHONY: help venv venv-api venv-worker venv-notifier \
        install install-api install-worker install-notifier \
        test-unit test-int test-e2e test-all test-cov test-all-cov \
        infra-up infra-down infra-test-up infra-test-down clean

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

# Python
PYTHON := python3

help:
	@echo "$(CYAN)FIAP X - Available Commands$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@echo "  make venv            Create virtual environments for all services"
	@echo "  make install         Install all dependencies (requires venv)"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  make infra-up        Start development infrastructure"
	@echo "  make infra-down      Stop development infrastructure"
	@echo ""
	@echo "$(GREEN)Testing:$(RESET)"
	@echo "  make test-unit       Run unit tests (fast, no deps)"
	@echo "  make test-int        Run integration tests (with mocks)"
	@echo "  make test-e2e        Run E2E tests (requires infra)"
	@echo "  make test-all        Run all tests"
	@echo "  make test-cov        Run API tests with coverage"
	@echo "  make test-all-cov    Run ALL tests with coverage"
	@echo ""
	@echo "$(GREEN)Test Infrastructure:$(RESET)"
	@echo "  make infra-test-up   Start test infrastructure"
	@echo "  make infra-test-down Stop test infrastructure"
	@echo ""
	@echo "$(GREEN)Cleanup:$(RESET)"
	@echo "  make clean           Remove cache and temp files"
	@echo "  make clean-venv      Remove all virtual environments"

# =============================================================================
# Virtual Environments
# =============================================================================

venv: venv-api venv-worker venv-notifier
	@echo "$(GREEN)All virtual environments created!$(RESET)"
	@echo ""
	@echo "To activate:"
	@echo "  API:      source fiapx-api/.venv/bin/activate"
	@echo "  Worker:   source fiapx-worker/.venv/bin/activate"
	@echo "  Notifier: source fiapx-notifier/.venv/bin/activate"

venv-api:
	@echo "$(CYAN)Creating venv for fiapx-api...$(RESET)"
	cd fiapx-api && $(PYTHON) -m venv .venv

venv-worker:
	@echo "$(CYAN)Creating venv for fiapx-worker...$(RESET)"
	cd fiapx-worker && $(PYTHON) -m venv .venv

venv-notifier:
	@echo "$(CYAN)Creating venv for fiapx-notifier...$(RESET)"
	cd fiapx-notifier && $(PYTHON) -m venv .venv

# =============================================================================
# Installation
# =============================================================================

install: install-api install-worker install-notifier
	@echo "$(GREEN)All dependencies installed!$(RESET)"

install-api:
	@echo "$(CYAN)Installing fiapx-api dependencies...$(RESET)"
	cd fiapx-api && .venv/bin/pip install --upgrade pip && \
		.venv/bin/pip install -r requirements.txt -r requirements-test.txt

install-worker:
	@echo "$(CYAN)Installing fiapx-worker dependencies...$(RESET)"
	cd fiapx-worker && .venv/bin/pip install --upgrade pip && \
		.venv/bin/pip install -r requirements.txt -r requirements-test.txt

install-notifier:
	@echo "$(CYAN)Installing fiapx-notifier dependencies...$(RESET)"
	cd fiapx-notifier && .venv/bin/pip install --upgrade pip && \
		.venv/bin/pip install -r requirements.txt -r requirements-test.txt

# =============================================================================
# Development Infrastructure
# =============================================================================

infra-up:
	@echo "$(CYAN)Starting development infrastructure...$(RESET)"
	cd infra && docker-compose up -d
	@echo "$(GREEN)Infrastructure started!$(RESET)"
	@echo "API: http://localhost:8000"
	@echo "RabbitMQ: http://localhost:15672"
	@echo "MinIO: http://localhost:9001"
	@echo "Grafana: http://localhost:3000"

infra-down:
	@echo "$(CYAN)Stopping development infrastructure...$(RESET)"
	cd infra && docker-compose down

# =============================================================================
# Test Infrastructure
# =============================================================================

infra-test-up:
	@echo "$(CYAN)Starting test infrastructure...$(RESET)"
	docker-compose -f infra/docker-compose.test.yml up -d
	@echo "$(GREEN)Test infrastructure started!$(RESET)"
	@echo "PostgreSQL: localhost:5434"
	@echo "Redis: localhost:6381"
	@echo "RabbitMQ: localhost:5673"
	@echo "MinIO: localhost:9002"

infra-test-down:
	@echo "$(CYAN)Stopping test infrastructure...$(RESET)"
	docker-compose -f infra/docker-compose.test.yml down -v

# =============================================================================
# Unit Tests (Fast, no external dependencies)
# =============================================================================

test-unit:
	@echo "$(CYAN)Running unit tests...$(RESET)"
	@echo ""
	@echo "$(YELLOW)=== fiapx-api ===$(RESET)"
	cd fiapx-api && .venv/bin/pytest tests/unit -v
	@echo ""
	@echo "$(YELLOW)=== fiapx-worker ===$(RESET)"
	cd fiapx-worker && .venv/bin/pytest tests/unit -v
	@echo ""
	@echo "$(YELLOW)=== fiapx-notifier ===$(RESET)"
	cd fiapx-notifier && .venv/bin/pytest tests/unit -v
	@echo ""
	@echo "$(GREEN)Unit tests completed!$(RESET)"

# =============================================================================
# Integration Tests (With mocked external services)
# =============================================================================

test-int:
	@echo "$(CYAN)Running integration tests...$(RESET)"
	@echo ""
	@echo "$(YELLOW)=== fiapx-api ===$(RESET)"
	cd fiapx-api && .venv/bin/pytest tests/integration -v
	@echo ""
	@echo "$(GREEN)Integration tests completed!$(RESET)"

# =============================================================================
# E2E Tests (Requires full infrastructure)
# =============================================================================

test-e2e:
	@echo "$(CYAN)Running E2E tests...$(RESET)"
	@echo "$(YELLOW)Note: Requires infrastructure to be running (make infra-up)$(RESET)"
	cd fiapx-api && .venv/bin/pytest ../tests/e2e -v
	@echo "$(GREEN)E2E tests completed!$(RESET)"

# =============================================================================
# All Tests
# =============================================================================

test-all: test-unit test-int
	@echo "$(GREEN)All tests completed!$(RESET)"

# =============================================================================
# Coverage Report
# =============================================================================

test-cov:
	@echo "$(CYAN)Running tests with coverage...$(RESET)"
	@echo ""
	@echo "$(YELLOW)=== fiapx-api ===$(RESET)"
	cd fiapx-api && .venv/bin/pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "$(GREEN)Coverage report generated at fiapx-api/htmlcov/index.html$(RESET)"

test-all-cov:
	@echo "$(CYAN)Running all tests with coverage...$(RESET)"
	@echo ""
	@echo "$(YELLOW)=== fiapx-api ===$(RESET)"
	cd fiapx-api && .venv/bin/pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "$(YELLOW)=== fiapx-worker ===$(RESET)"
	cd fiapx-worker && .venv/bin/pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "$(YELLOW)=== fiapx-notifier ===$(RESET)"
	cd fiapx-notifier && .venv/bin/pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "$(GREEN)All tests completed with coverage!$(RESET)"
	@echo "Coverage reports:"
	@echo "  API:      fiapx-api/htmlcov/index.html"
	@echo "  Worker:   fiapx-worker/htmlcov/index.html"
	@echo "  Notifier: fiapx-notifier/htmlcov/index.html"

# =============================================================================
# API Tests Only
# =============================================================================

test-api-unit:
	@echo "$(CYAN)Running fiapx-api unit tests...$(RESET)"
	cd fiapx-api && .venv/bin/pytest tests/unit -v

test-api-int:
	@echo "$(CYAN)Running fiapx-api integration tests...$(RESET)"
	cd fiapx-api && .venv/bin/pytest tests/integration -v

test-api:
	@echo "$(CYAN)Running all fiapx-api tests...$(RESET)"
	cd fiapx-api && .venv/bin/pytest tests/ -v

# =============================================================================
# Worker Tests Only
# =============================================================================

test-worker-unit:
	@echo "$(CYAN)Running fiapx-worker unit tests...$(RESET)"
	cd fiapx-worker && .venv/bin/pytest tests/unit -v

test-worker:
	@echo "$(CYAN)Running all fiapx-worker tests...$(RESET)"
	cd fiapx-worker && .venv/bin/pytest tests/ -v

# =============================================================================
# Notifier Tests Only
# =============================================================================

test-notifier-unit:
	@echo "$(CYAN)Running fiapx-notifier unit tests...$(RESET)"
	cd fiapx-notifier && .venv/bin/pytest tests/unit -v

test-notifier:
	@echo "$(CYAN)Running all fiapx-notifier tests...$(RESET)"
	cd fiapx-notifier && .venv/bin/pytest tests/ -v

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "$(CYAN)Cleaning up...$(RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup completed!$(RESET)"

clean-venv:
	@echo "$(CYAN)Removing virtual environments...$(RESET)"
	rm -rf fiapx-api/.venv
	rm -rf fiapx-worker/.venv
	rm -rf fiapx-notifier/.venv
	@echo "$(GREEN)Virtual environments removed!$(RESET)"
