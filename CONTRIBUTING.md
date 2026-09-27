# Contributing to Agent Identity Security Control Plane

Thank you for your interest in contributing. This document describes how to set up
your development environment, coding standards, and the pull request process.

## Table of Contents

- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Commit Message Format](#commit-message-format)
- [Security Contributions](#security-contributions)

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose
- Terraform 1.8+
- pre-commit

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/kogunlowo123/agent-identity-security-control-plane.git
cd agent-identity-security-control-plane

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Copy environment file
cp .env.example .env

# Start local infrastructure
docker-compose up -d postgres opensearch opa

# Install service dependencies
cd services/api && uv sync
cd ../agent-runtime && uv sync
cd ../rag-core && uv sync
```

### Running the Full Stack Locally

```bash
docker-compose up -d
# API available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Coding Standards

### Python

- **Python 3.12+** with full type hints
- **pydantic v2** for data validation
- **ruff** for linting and formatting (configured in pyproject.toml)
- **mypy** for type checking (strict mode)
- Maximum line length: 120 characters
- No mutable default arguments
- All async code uses `async`/`await` consistently

Run linting:

```bash
make lint       # ruff check + ruff format --check
make type-check # mypy
```

### Terraform

- All resources tagged with `environment`, `project`, `managed_by=terraform`
- Use `for_each` over `count` for multi-instance resources
- Separate state per environment
- `terraform fmt` enforced by pre-commit

### Documentation

- All public functions/classes must have docstrings
- New features require architecture decision records (ADRs) in `docs/adr/`
- Runbooks for operational procedures in `docs/runbooks/`

## Testing Requirements

All pull requests must:

1. **Pass all existing tests**: `make test`
2. **Add tests for new functionality**: Unit tests for business logic, integration tests for API endpoints
3. **Maintain or improve coverage**: Target >80% line coverage
4. **Include security tests** for any identity/delegation changes

Test structure:
```
tests/
├── unit/          # Pure unit tests, no I/O
├── integration/   # API + database integration tests
└── security/      # Security property tests
```

Run tests:
```bash
make test-unit
make test-integration
make test-security
```

## Pull Request Process

1. **Fork** the repository and create your branch from `main`
2. **Name your branch**: `feat/short-description`, `fix/short-description`, `chore/short-description`
3. **Write tests** for your changes
4. **Run the full test suite**: `make test`
5. **Run pre-commit**: `pre-commit run --all-files`
6. **Submit the PR** using the PR template
7. **Address review feedback** promptly

### PR Checklist

- [ ] Tests pass locally
- [ ] Pre-commit hooks pass
- [ ] Documentation updated if needed
- [ ] ADR added if architectural decision made
- [ ] Security implications considered

### Review Requirements

- At least 1 approval required
- Security-sensitive changes (identity/, security/, .github/workflows/) require maintainer approval
- CI must pass (lint, type-check, tests, security scan)

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `security`

Scopes: `api`, `identity`, `agent-runtime`, `rag-core`, `infra`, `deploy`, `security`

Examples:
```
feat(identity): add token rotation endpoint for T0 agents
fix(api): handle expired SVID in /validate endpoint
security(opa): strengthen delegation depth check policy
```

## Security Contributions

For security vulnerabilities, see [SECURITY.md](SECURITY.md) for responsible disclosure.

For general security improvements (hardening, new policies, detection rules):
1. Open an issue first to discuss the approach
2. Reference any relevant standards (NIST, OWASP, etc.)
3. Include threat model context
