# Changelog

All notable changes to the ZakupAI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Core Services**: FastAPI microservices for calculation, risk assessment, document generation, and embeddings
- **Database Layer**: PostgreSQL with Alembic migrations and automated schema management
- **API Gateway**: Nginx reverse proxy with rate limiting, CORS policies, and security headers
- **AI Integration**: Ollama embeddings, ChromaDB vector storage, and Flowise workflow automation
- **Telegram Bot**: aiogram 3-based bot with /start, /lot commands, and hot lots notifications
- **Web Panel**: FastAPI web interface with lot analysis pages and CSV/XLSX price upload functionality
- **n8n Workflow Nodes**: Custom TypeScript nodes for price aggregation, risk scoring, and document building
- **Multi-language Support**: Localization system with ru-KZ, en, and ru language packs
- **E2E Testing Framework**: Complete pipeline tests from price import to risk evaluation
- **Environment Management**: Separate dev/stage/prod configurations with security policies
- **Database Backup System**: Automated PostgreSQL backups to Backblaze B2 with 14-day retention
- **Monitoring Stack**: Prometheus, Grafana, Alertmanager with container metrics and health checks
- **Security Features**: API key authentication, CSRF protection, audit logging, and input validation

### Changed

- **CORS Configuration**: Environment-specific origin allowlisting for dev/stage/prod
- **Rate Limiting**: Tiered limits based on environment (300/120/60 req/min)
- **Security Headers**: Comprehensive CSP, HSTS, and security headers in production
- **Docker Compose**: Multi-environment support with profiles and resource limits

### Fixed

- **Type Safety**: Resolved Pylance type errors across all services
- **Database Constraints**: Added proper foreign key cascades for lot_prices table
- **Gateway Configuration**: Fixed proxy headers and health check pass-through
- **Container Dependencies**: Proper service dependency chains and health checks

### Security

- **Input Validation**: Comprehensive Pydantic validation for all API endpoints
- **Secret Management**: Environment-based configuration with placeholder values
- **Audit Logging**: Security event tracking across all services
- **Container Security**: Non-root users and resource constraints

## [1.0.0] - 2024-08-30

### Added

- Initial release of ZakupAI MVP platform
- Government procurement lot analysis and automation
- Risk scoring and margin calculation capabilities
- Multi-service architecture with Docker containerization
