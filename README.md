# LLT Assistant Backend

**A comprehensive FastAPI backend for pytest test analysis and generation** using hybrid AI-powered approaches.

## Overview

LLT Assistant Backend is an intelligent testing assistant that helps developers improve their Python test suites through automated analysis, generation, and optimization. It combines rule-based static analysis with Large Language Model (LLM) intelligence and graph database dependency tracking.

## Core Features

### Feature 1: Test Generation
**AI-powered test code generation** using Large Language Models
- Generate pytest tests from source code and user descriptions
- Support for existing test context and regeneration scenarios
- Asynchronous processing with polling-based status checks
- **Technology**: OpenAI-compatible LLM APIs, Redis task queue
- **Endpoint**: `POST /workflows/generate-tests`

### Feature 2: Coverage Optimization
**Targeted test generation** to fill specific coverage gaps
- Generate tests for uncovered code lines and branches
- Coverage-aware generation with insertion line guidance
- Integration with Coverage.py analysis results
- **Technology**: LLM-based with coverage data analysis
- **Endpoint**: `POST /optimization/coverage`

### Feature 3: Impact Analysis
**Graph-based dependency analysis** to determine which tests are affected by code changes
- Function-level precision using git diff parsing
- Reverse dependency traversal (2-level deep)
- 90-95% accuracy vs 60-70% for file-level heuristics
- **Technology**: Neo4j graph database (mandatory)
- **Endpoint**: `POST /analysis/impact`

### Feature 4: Quality Analysis
**Comprehensive test quality assessment** with rule-based and LLM analysis
- 6 detection rules: redundant assertions, missing assertions, trivial assertions, unused fixtures, unused variables, missing mocks
- Multiple analysis modes: fast (rules-only), deep (LLM), hybrid
- Optional Neo4j integration for enhanced mock detection
- Actionable fix suggestions with code changes
- **Technology**: AST parsing, optional Neo4j, optional LLM
- **Endpoint**: `POST /quality/analyze`

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                    (Python 3.11+ / Async)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API Layer (app/api/v1/)                             │  │
│  │  - Feature 1 & 2: Test Generation & Coverage         │  │
│  │  - Feature 3: Impact Analysis                        │  │
│  │  - Feature 4: Quality Analysis                       │  │
│  │  - Context Management (Neo4j ingestion)              │  │
│  │  - Debug Endpoints                                   │  │
│  └────────────┬─────────────────────────────────────────┘  │
│               │                                              │
│  ┌────────────┴─────────────────────────────────────────┐  │
│  │  Service Layer (app/core/)                           │  │
│  │  ┌─────────────┬──────────────┬──────────────────┐  │  │
│  │  │ Test        │ Quality      │ Impact           │  │  │
│  │  │ Analyzer    │ Service      │ Analyzer         │  │  │
│  │  └─────────────┴──────────────┴──────────────────┘  │  │
│  └──────┬──────────────┬──────────────┬────────────────┘  │
│         │              │              │                     │
│  ┌──────▼──────┐  ┌───▼──────┐  ┌────▼────────┐          │
│  │ Rule Engine │  │ LLM      │  │ Graph       │          │
│  │ (AST-based) │  │ Client   │  │ Service     │          │
│  │ 6 Detection │  │ (httpx)  │  │ (Neo4j)     │          │
│  │ Rules       │  │          │  │ Async Pool  │          │
│  └─────────────┘  └──────────┘  └─────────────┘          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │                    │                   │
         ▼                    ▼                   ▼
┌────────────────┐   ┌─────────────────┐   ┌──────────────┐
│ Redis          │   │ LLM API         │   │ Neo4j 5.13+  │
│ (Task Queue)   │   │ (OpenAI-compat) │   │ (Graph DB)   │
│ Optional       │   │ Features 1,2,4  │   │ Features 3,4 │
│ In-mem fallback│   │                 │   │              │
└────────────────┘   └─────────────────┘   └──────────────┘
```

### Technology Stack

**Core Framework**
- **FastAPI 0.104+**: High-performance async web framework
- **Python 3.11+**: Modern async/await support
- **Pydantic 2.5+**: Data validation and settings management
- **Uvicorn**: ASGI server

**Analysis & AI**
- **AST Parsing**: Python's built-in `ast` module for static analysis
- **LLM Integration**: httpx async client with OpenAI-compatible APIs
- **Models Supported**: GPT-4, Claude, DeepSeek, or any OpenAI-compatible API

**Data Storage**
- **Neo4j 5.13+**: Graph database for code dependency tracking
- **Redis 7+**: Task queue and caching (optional, in-memory fallback available)

**Development & Testing**
- **pytest**: Test framework with async support
- **Docker & Docker Compose**: Containerized deployment
- **uv**: Fast Python package manager (primary)
- **Nix**: Experimental reproducible build system

### Feature Dependency Matrix

| Feature | Neo4j Required | Redis Required | LLM Required |
|---------|---------------|----------------|--------------|
| Feature 1: Test Generation | ❌ No | ⚠️ Optional* | ✅ Yes |
| Feature 2: Coverage Optimization | ❌ No | ⚠️ Optional* | ✅ Yes |
| Feature 3: Impact Analysis | ✅ Yes (mandatory) | ❌ No | ❌ No |
| Feature 4: Quality Analysis | ⚠️ Optional** | ❌ No | ⚠️ Optional*** |

**Notes:**
- *Redis is optional with automatic in-memory fallback for Features 1 & 2
- **Neo4j enhances mock detection accuracy in Feature 4 but not required
- ***LLM required only for "deep" or "hybrid" analysis modes; "fast" mode uses rules only

## Quick Start

### Prerequisites

- **Python 3.11+** - Required for all builds
- **Docker & Docker Compose** - Recommended for deployment
- **uv package manager** - For standard development (install: `pip install uv`)
- **LLM API Key** - Required for Features 1, 2, and Feature 4 (deep/hybrid modes)

### Option 1: Docker Deployment (Recommended)

**Best for:** Production use, full feature testing, complete development environment

```bash
# 1. Clone the repository
git clone <repository-url>
cd LLT-Assistant-Backend

# 2. Configure environment variables
cp .env.example .env
# Edit .env and set:
#   - LLM_API_KEY=your-api-key-here
#   - Other settings as needed

# 3. Start all services (Redis, Neo4j, API)
docker-compose up -d

# 4. Verify services are running
docker-compose ps

# 5. Access the application
# - API Documentation: http://localhost:8886/docs
# - Health Check: http://localhost:8886/health
# - Neo4j Browser: http://localhost:7474 (credentials: neo4j/neo4j123)
```

**Services included:**
- **API Service** (port 8886): FastAPI backend
- **Redis** (port 6379): Task queue for Features 1 & 2
- **Neo4j** (ports 7474, 7687): Graph database for Features 3 & 4

### Option 2: Local Development (Standard Build)

**Best for:** Lightweight development, API-only testing without graph features

```bash
# 1. Install dependencies
uv pip install -e .

# 2. Set up environment variables
cp .env.example .env
# Edit .env to add LLM_API_KEY

# 3. (Optional) Start Redis locally
# If not available, system will use in-memory fallback

# 4. (Optional) Start Neo4j locally
# docker-compose up -d neo4j
# Without Neo4j: Feature 3 returns 503, Feature 4 falls back to AST-only

# 5. Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8886

# 6. Access API
# - Documentation: http://localhost:8886/docs
# - Health Check: http://localhost:8886/health
```

### Option 3: Nix Build (Experimental)

**Best for:** Reproducible builds, Nix enthusiasts

This is currently in POC phase. See `CLAUDE.md` section 13 for detailed instructions.

```bash
# Build Python application
nix build .

# Enter development shell
nix develop

# Build Docker image
nix build .#dockerImage
```

## API Usage

### Available Endpoints

**Test Analysis & Generation:**
- `POST /workflows/generate-tests` - Generate new pytest tests (Feature 1)
- `POST /optimization/coverage` - Generate tests for coverage gaps (Feature 2)
- `POST /analysis/impact` - Analyze test impact from code changes (Feature 3)
- `POST /quality/analyze` - Analyze test quality issues (Feature 4)

**Task Management:**
- `GET /tasks/{task_id}` - Poll async task status (Features 1 & 2)

**Context Management:**
- `POST /context/ingest` - Ingest code symbols into graph database
- `GET /context/projects/{project_id}` - Retrieve project data from graph
- `GET /context/query-function/{function_name}` - Query function dependencies
- `DELETE /context/projects/{project_id}` - Clear project data

**Utility:**
- `GET /health` - Health check with service status
- `GET /` - API information

### Example: Quality Analysis (Feature 4)

Analyze test files for quality issues with actionable fix suggestions.

**Request:**
```bash
curl -X POST http://localhost:8886/quality/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "path": "tests/test_example.py",
        "content": "def test_example():\n    assert True\n    assert True  # Redundant\n"
      }
    ],
    "mode": "fast"
  }'
```
**Response:**
```json
{
  "analysis_id": "uuid-123",
  "summary": {
    "total_files": 1,
    "total_issues": 1,
    "critical_issues": 0
  },
  "issues": [
    {
      "file_path": "tests/test_example.py",
      "line": 3,
      "severity": "warning",
      "code": "redundant-assertion",
      "message": "Duplicate assertion detected",
      "detected_by": "rule",
      "suggestion": {
        "type": "delete",
        "new_text": null,
        "description": "Remove this duplicate assertion to reduce redundancy"
      }
    }
  ]
}
```

### Example: Impact Analysis (Feature 3)

Analyze which tests are affected by code changes using graph dependencies.

**Request:**
```bash
curl -X POST http://localhost:8886/analysis/impact \
  -H "Content-Type: application/json" \
  -d '{
    "project_context": {
      "files_changed": ["src/payment.py"],
      "related_tests": []
    },
    "git_diff": "diff --git a/src/payment.py\n+def process_payment():\n+    pass",
    "project_id": "my-project"
  }'
```

**Response:**
```json
{
  "impacted_tests": [
    {
      "test_path": "tests/test_payment.py",
      "impact_score": 0.9,
      "severity": "high",
      "reasons": ["Test directly tests modified function process_payment"]
    }
  ],
  "severity": "high",
  "suggested_action": "run-affected-tests"
}
```

For more examples, see the interactive API documentation at `/docs` when the server is running.

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

**LLM Configuration** (Required for Features 1, 2, 4-deep/hybrid):
```env
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1  # Or compatible endpoint
LLM_MODEL=gpt-4
LLM_TIMEOUT=120
LLM_MAX_RETRIES=3
```

**Neo4j Configuration** (Required for Feature 3, optional for Feature 4):
```env
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j123
NEO4J_DATABASE=neo4j
```

**Redis Configuration** (Optional - in-memory fallback available):
```env
REDIS_URL=redis://redis:6379/0
```

**Application Settings:**
```env
LOG_LEVEL=INFO
LOG_FORMAT=json
DEBUG=false
MAX_FILES_PER_REQUEST=50
MAX_FILE_SIZE=1048576
```

## Development

### Project Structure

```
llt-assistant-backend/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management (env vars)
│   │
│   ├── api/v1/                    # API layer
│   │   ├── routes.py              # Main API endpoints (Features 1-4)
│   │   ├── context.py             # Context/graph ingestion endpoints
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── debug_routes.py        # Debug endpoints for Neo4j
│   │
│   ├── core/                      # Core business logic
│   │   ├── analyzer.py            # Test & Impact analyzers
│   │   ├── constants.py           # Issue types and constants
│   │   ├── protocols.py           # Type protocols
│   │   │
│   │   ├── analysis/              # Analysis strategies
│   │   │   ├── llm_analyzer.py    # LLM-based analysis
│   │   │   ├── strategies.py      # Analysis mode strategies
│   │   │   └── uncertain_case_detector.py
│   │   │
│   │   ├── graph/                 # Neo4j integration
│   │   │   ├── neo4j_client.py    # Async Neo4j driver wrapper
│   │   │   └── graph_service.py   # Graph operations service
│   │   │
│   │   ├── llm/                   # LLM integration
│   │   │   └── llm_client.py      # OpenAI-compatible client
│   │   │
│   │   ├── services/              # Service layer
│   │   │   ├── quality_service.py # Quality analysis orchestrator
│   │   │   └── logging_config.py  # Structured logging
│   │   │
│   │   ├── tasks/                 # Async task management
│   │   │   ├── tasks.py           # Task execution and storage
│   │   │   └── in_memory_tasks.py # In-memory fallback
│   │   │
│   │   └── utils/                 # Utilities
│   │       ├── diff_parser.py     # Git diff parsing
│   │       ├── change_classifier.py # Functional vs non-functional
│   │       ├── json_extractor.py  # JSON response extraction
│   │       └── module_resolver.py # Python module resolution
│   │
│   ├── analyzers/                 # Analysis engines
│   │   ├── ast_parser.py          # Python AST parsing
│   │   └── rule_engine.py         # 6 quality detection rules
│   │
│   └── models/                    # Data models
│       ├── context.py             # Graph/context models
│       └── (other models)
│
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (no external deps)
│   ├── integration/               # Integration tests (require Neo4j)
│   └── fixtures/                  # Test fixtures and sample data
│
├── docs/                          # Documentation
│   ├── feat/                      # Feature documentation
│   ├── context/                   # Architecture context
│   ├── testing/                   # Testing guides
│   └── tasks/                     # Task tracking
│
├── docker-compose.yml             # Service orchestration
├── Dockerfile                     # Container definition
├── pyproject.toml                 # Project dependencies (PEP 621)
├── uv.lock                        # Dependency lock file
├── flake.nix                      # Nix build definition (experimental)
├── CLAUDE.md                      # Coding standards and guidelines
└── README.md                      # This file
```

### Running Tests

**Unit Tests** (no external dependencies required):
```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run all unit tests
pytest tests/unit/ -v

# Run with coverage report
pytest tests/unit/ --cov=app --cov-report=html
```

**Integration Tests** (requires Neo4j running):
```bash
# Start Neo4j
docker-compose up -d neo4j

# Run integration tests with local Neo4j
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=neo4j123 \
NEO4J_DATABASE=neo4j \
pytest tests/integration/ -v -m integration

# Stop Neo4j when done
docker-compose down neo4j
```

**Important:** When running tests locally (outside Docker), use `NEO4J_URI=bolt://localhost:7687`. Inside Docker containers, use `bolt://neo4j:7687`.

### Code Quality Tools

The project uses automated code quality tools:

```bash
# Format code with Black
black app/ tests/

# Sort imports with isort
isort app/ tests/

# Type checking with mypy
mypy app/

# Run all quality checks
pre-commit run --all-files
```

## Additional Resources

### Documentation

- **Feature Documentation**: See `docs/feat/` for detailed architecture of each feature
  - [Feature 1: Test Generation](docs/feat/feat1-test-generation.md)
  - [Feature 2: Coverage Optimization](docs/feat/feat2-coverage-optimization.md)
  - [Feature 3: Impact Analysis](docs/feat/feat3-impact-analysis.md)
  - [Feature 4: Quality Analysis](docs/feat/feat4-quality-analyse.md)
- **Neo4j Integration**: See [docs/context/neo4j-integration.md](docs/context/neo4j-integration.md)
- **Coding Standards**: See [CLAUDE.md](CLAUDE.md) for contribution guidelines
- **API Specification**: Interactive docs at `/docs` when server is running

### Neo4j Graph Database

The project uses Neo4j for storing code dependency graphs. Key capabilities:

- **Data Model**: Stores functions, classes, methods as `Symbol` nodes
- **Relationships**: Tracks `CALLS` (function calls) and `IMPORTS` (module imports)
- **Query Performance**: <100ms for typical dependency queries
- **Multi-Project**: Isolates data by `project_id`

**Quick Access:**
- Neo4j Browser UI: http://localhost:7474
- Default credentials: `neo4j` / `neo4j123`
- Bolt protocol: `bolt://localhost:7687`

**Ingestion Workflow:**
```bash
# 1. Parse code symbols (frontend/LSP parser)
# 2. Send to backend via POST /context/ingest
# 3. Query dependencies via GET /context/query-function/{name}
```

See [docs/context/neo4j-integration.md](docs/context/neo4j-integration.md) for complete documentation.

### Performance Characteristics

| Feature | Typical Latency | Bottleneck |
|---------|----------------|------------|
| Feature 1: Test Generation | 5-30 seconds | LLM API call |
| Feature 2: Coverage Optimization | 8-40 seconds | LLM API call |
| Feature 3: Impact Analysis | 150-300ms | Neo4j queries |
| Feature 4: Quality Analysis | 100-500ms | AST parsing + optional Neo4j |

### Production Deployment

**Recommended Stack:**
- **Load Balancer**: Nginx or cloud load balancer
- **API**: 2-4 FastAPI instances (Docker containers)
- **Neo4j**: Managed service or dedicated instance
- **Redis**: Redis Cloud or ElastiCache (optional)
- **LLM API**: OpenAI, Azure OpenAI, or self-hosted

**Scaling Considerations:**
- API is stateless and can scale horizontally
- Neo4j benefits from vertical scaling (more RAM)
- LLM rate limits may require request queuing
- Monitor `/health` endpoint for service availability

**Security:**
- Configure CORS for specific domains (not `*`)
- Use HTTPS for all external communication
- Rotate LLM API keys regularly
- Network isolation for Neo4j and Redis

### Contributing

We welcome contributions! Please:

1. Read [CLAUDE.md](CLAUDE.md) for coding standards
2. Write tests for new features
3. Follow conventional commit format
4. Ensure all tests pass before submitting PR
5. Update documentation as needed

### License

MIT License - see LICENSE file for details.

### Support & Issues

For questions or issues:
1. Check documentation in `docs/`
2. Search existing GitHub issues
3. Create new issue with detailed description and reproduction steps

---

**Project Status:** Production Ready
**Version:** 0.1.0
**Last Updated:** 2025-11-27
