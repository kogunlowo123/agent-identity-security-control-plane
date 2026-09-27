.PHONY: help install lint type-check test test-unit test-integration test-security \
        build docker-build docker-push tf-init tf-plan tf-apply clean

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3.12
UV := uv
DOCKER_REGISTRY := gcr.io/your-gcp-project
IMAGE_TAG := $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")
SERVICES := services/api services/agent-runtime services/rag-core

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all service dependencies
	@for svc in $(SERVICES); do \
		echo "Installing $$svc..."; \
		cd $$svc && $(UV) sync && cd ../..; \
	done
	@cd tools/agentctl && $(UV) sync && cd ../..

lint: ## Run ruff linter and formatter check
	@for svc in $(SERVICES) tools/agentctl; do \
		echo "Linting $$svc..."; \
		cd $$svc && $(UV) run ruff check src/ && $(UV) run ruff format --check src/ && cd ../..; \
	done
	@$(UV) run --with ruff ruff check identity/issuance/broker/
	@$(UV) run --with ruff ruff check identity/session/revocation/

type-check: ## Run mypy type checker
	@for svc in $(SERVICES) tools/agentctl; do \
		echo "Type checking $$svc..."; \
		cd $$svc && $(UV) run mypy src/ && cd ../..; \
	done

test: test-unit test-integration test-security ## Run all tests

test-unit: ## Run unit tests
	cd services/api && $(UV) run pytest ../../tests/unit/ -v --tb=short -x \
		--cov=src --cov-report=term-missing --cov-report=xml:coverage.xml

test-integration: ## Run integration tests
	cd services/api && $(UV) run pytest ../../tests/integration/ -v --tb=short \
		-m integration --asyncio-mode=auto

test-security: ## Run security tests
	cd services/api && $(UV) run pytest ../../tests/security/ -v --tb=short \
		-m security

build: ## Build Python packages
	@for svc in $(SERVICES); do \
		echo "Building $$svc..."; \
		cd $$svc && $(UV) build && cd ../..; \
	done

docker-build: ## Build Docker images
	docker build -t $(DOCKER_REGISTRY)/api:$(IMAGE_TAG) services/api/
	docker build -t $(DOCKER_REGISTRY)/agent-runtime:$(IMAGE_TAG) services/agent-runtime/
	docker build -t $(DOCKER_REGISTRY)/rag-core:$(IMAGE_TAG) services/rag-core/
	docker build -t $(DOCKER_REGISTRY)/broker:$(IMAGE_TAG) identity/issuance/broker/

docker-push: docker-build ## Build and push Docker images
	docker push $(DOCKER_REGISTRY)/api:$(IMAGE_TAG)
	docker push $(DOCKER_REGISTRY)/agent-runtime:$(IMAGE_TAG)
	docker push $(DOCKER_REGISTRY)/rag-core:$(IMAGE_TAG)
	docker push $(DOCKER_REGISTRY)/broker:$(IMAGE_TAG)

tf-init: ## Initialize Terraform for the target environment (ENV=dev|staging|prod)
	ENV ?= dev
	cd infra/envs/gcp/$(ENV) && terraform init

tf-plan: ## Run Terraform plan (ENV=dev|staging|prod)
	ENV ?= dev
	cd infra/envs/gcp/$(ENV) && terraform plan -out=tfplan

tf-apply: ## Apply Terraform plan (ENV=dev|staging|prod)
	ENV ?= dev
	cd infra/envs/gcp/$(ENV) && terraform apply tfplan

tf-fmt: ## Format Terraform files
	terraform fmt -recursive infra/

tf-validate: ## Validate Terraform files
	@for env in infra/envs/gcp/*/; do \
		echo "Validating $$env..."; \
		cd $$env && terraform validate && cd ../../../..; \
	done

evals: ## Run evaluation suite
	cd services/api && $(UV) run python ../../evals/runners/ci_gate.py

scaffold-agent: ## Scaffold a new agent (NAME=my-agent TIER=T1)
	cd tools/agentctl && $(UV) run agentctl scaffold --name $(NAME) --tier $(TIER)

validate-registry: ## Validate all agent YAML files in the registry
	cd tools/agentctl && $(UV) run agentctl validate --dir ../../identity/registry/agents/

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "coverage.xml" -delete 2>/dev/null || true
	find . -name "tfplan" -delete 2>/dev/null || true
