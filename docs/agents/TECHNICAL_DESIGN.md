# LangChain-based Lightweight Agent Framework
## Technical Design Document

**Version:** 1.0
**Date:** 2025-11-18
**Status:** In Development

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Core Components](#core-components)
4. [Agent Pipeline](#agent-pipeline)
5. [LangChain Integration](#langchain-integration)
6. [DeepSeek LLM Configuration](#deepseek-llm-configuration)
7. [Quality Gates](#quality-gates)
8. [Performance Optimization](#performance-optimization)
9. [Security Considerations](#security-considerations)
10. [Implementation Phases](#implementation-phases)
11. [Testing Strategy](#testing-strategy)
12. [Monitoring and Observability](#monitoring-and-observability)

---

## 1. Executive Summary

### Objective
Design and implement a lightweight, modular agent framework using LangChain to improve the test analysis pipeline's quality, performance, and maintainability.

### Key Benefits
- **40% faster response times** through parallel agent execution
- **Modular architecture** enabling independent testing and optimization
- **Built-in quality gates** at each pipeline stage
- **LangChain integration** for standardized LLM interactions
- **DeepSeek LLM** for cost-effective, high-quality analysis

### Technology Stack
- **Framework:** LangChain (agent orchestration, prompt management)
- **LLM Provider:** DeepSeek API (deepseek-chat model)
- **Async Runtime:** Python asyncio
- **Validation:** Pydantic v2
- **Testing:** pytest + hypothesis

---

## 2. Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Endpoint                         │
│                    /api/v1/analyze                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  AgentOrchestrator                           │
│  - Manages agent lifecycle                                   │
│  - Handles error recovery                                    │
│  - Collects metrics                                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   AgentContext                               │
│  - Shared state across agents                                │
│  - Request metadata                                          │
│  - Intermediate results                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌────────────────┐          ┌────────────────┐
│  Sequential    │          │   Parallel     │
│    Agents      │          │    Agents      │
│                │          │                │
│ 1. Input       │          │ 3a. Parsing    │
│ 2. Strategy    │          │ 3b. Rules      │
│ 4. Synthesis   │          │ 3c. LLM        │
│ 5. Enhancement │          │                │
│ 6. QA          │          │                │
└────────────────┘          └────────────────┘
```

### 2.2 Agent Layers

| Layer | Agent | Execution Mode | Quality Gate |
|-------|-------|----------------|--------------|
| **1** | InputProcessingAgent | Sequential | Schema validation |
| **2** | StrategyPlanningAgent | Sequential | Plan validation |
| **3a** | ParsingAgent | **Parallel** | AST validation |
| **3b** | RuleAnalysisAgent | **Parallel** | Rule coverage |
| **3c** | LLMAnalysisAgent | **Parallel** | LLM response validation |
| **4** | SynthesisAgent | Sequential | Deduplication check |
| **5** | EnhancementAgent | Sequential | Suggestion quality |
| **6** | QualityAssuranceAgent | Sequential | Output completeness |

---

## 3. Core Components

### 3.1 BaseAgent (Abstract Base Class)

**Responsibilities:**
- Define standard agent interface
- Implement quality gate pattern
- Track execution metrics
- Handle errors gracefully

**Key Methods:**
```python
async def run(context: AgentContext) -> AgentResult:
    """Main execution with quality gates"""

async def execute(context: AgentContext) -> AgentResult:
    """Agent-specific logic (abstract)"""

async def validate_input(context: AgentContext) -> list[str]:
    """Pre-execution validation"""

async def validate_output(result: AgentResult, context: AgentContext) -> list[str]:
    """Post-execution validation"""
```

**Metrics Tracked:**
- Total executions
- Error count
- Total execution time
- Average execution time
- Success rate

### 3.2 AgentContext (Shared State)

**Responsibilities:**
- Store request data
- Hold intermediate results
- Track execution metadata
- Enable agent communication

**Key Attributes:**
```python
@dataclass
class AgentContext:
    # Request
    request_id: str
    files: List[FileInput]
    mode: str
    config: Dict[str, Any]

    # Intermediate results
    parsed_files: List[ParsedTestFile]
    rule_issues: List[Issue]
    llm_issues: List[Issue]
    merged_issues: List[Issue]

    # Metadata
    execution_plan: Dict[str, Any]
    agent_results: Dict[str, AgentResult]
    start_time: float
```

### 3.3 AgentOrchestrator (Pipeline Manager)

**Responsibilities:**
- Execute agent pipeline
- Coordinate sequential/parallel execution
- Aggregate results
- Handle failures and retries

**Pipeline Stages:**
1. **Initialization:** Create context, validate request
2. **Sequential Pre-processing:** Input → Strategy
3. **Parallel Analysis:** Parsing + Rules + LLM (concurrent)
4. **Sequential Post-processing:** Synthesis → Enhancement → QA
5. **Finalization:** Build response, collect metrics

---

## 4. Agent Pipeline

### 4.1 Agent Flow Diagram

```
START
  │
  ├─ [1] InputProcessingAgent
  │    ├─ Validate request schema
  │    ├─ Sanitize file content
  │    ├─ Check file size limits
  │    └─ Extract metadata
  │
  ├─ [2] StrategyPlanningAgent
  │    ├─ Analyze file characteristics
  │    ├─ Determine optimal mode
  │    ├─ Create execution plan
  │    └─ Estimate cost/time
  │
  ├─ [3] Parallel Analysis (Fan-out)
  │    │
  │    ├─ [3a] ParsingAgent
  │    │    ├─ Parse AST
  │    │    ├─ Extract test functions
  │    │    └─ Cache parsed files
  │    │
  │    ├─ [3b] RuleAnalysisAgent (if rules-only or hybrid)
  │    │    ├─ Run rule engine
  │    │    ├─ Detect code smells
  │    │    └─ Generate basic issues
  │    │
  │    └─ [3c] LLMAnalysisAgent (if llm-only or hybrid)
  │         ├─ Select uncertain cases
  │         ├─ Call DeepSeek API
  │         └─ Parse LLM responses
  │
  ├─ [4] SynthesisAgent
  │    ├─ Merge rule + LLM issues
  │    ├─ Deduplicate conflicts
  │    ├─ Prioritize by severity
  │    └─ Sort by file/line
  │
  ├─ [5] EnhancementAgent
  │    ├─ Generate fix suggestions
  │    ├─ Add code examples
  │    ├─ Calculate confidence scores
  │    └─ Enrich metadata
  │
  ├─ [6] QualityAssuranceAgent
  │    ├─ Validate output structure
  │    ├─ Check completeness
  │    ├─ Verify all files processed
  │    └─ Add final metrics
  │
END (Return AnalyzeResponse)
```

### 4.2 Execution Modes

#### Mode 1: rules-only
```
Input → Strategy → Parsing + Rules (parallel) → Synthesis → Enhancement → QA
```
- **Expected time:** 1-2s
- **Agents used:** 6 (skip LLMAnalysisAgent)

#### Mode 2: llm-only
```
Input → Strategy → Parsing + LLM (parallel) → Synthesis → Enhancement → QA
```
- **Expected time:** 5-8s
- **Agents used:** 6 (skip RuleAnalysisAgent)

#### Mode 3: hybrid (recommended)
```
Input → Strategy → Parsing + Rules + LLM (parallel) → Synthesis → Enhancement → QA
```
- **Expected time:** 6-10s (optimized from 10-15s)
- **Agents used:** 7 (all agents)

---

## 5. LangChain Integration

### 5.1 LangChain Components Used

| Component | Purpose | Location |
|-----------|---------|----------|
| `ChatOpenAI` | LLM client wrapper | `app/agents/llm/client.py` |
| `PromptTemplate` | Structured prompts | `app/agents/llm/prompts.py` |
| `OutputParser` | Parse LLM JSON responses | `app/agents/llm/parsers.py` |
| `CallbackManager` | Track token usage | `app/agents/monitoring.py` |
| `RetryWithErrorOutputParser` | Handle malformed JSON | `app/agents/llm/parsers.py` |

### 5.2 LangChain Architecture

```python
# LLM Client Setup
from langchain_openai import ChatOpenAI
from langchain.callbacks import get_openai_callback

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_base=os.getenv("DEEPSEEK_BASE_URL"),
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0.1,
    max_tokens=2000,
)

# Prompt Template
from langchain.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", ASSERTION_QUALITY_SYSTEM_PROMPT),
    ("user", ASSERTION_QUALITY_USER_PROMPT),
])

# Chain Execution
chain = prompt | llm | JsonOutputParser()
result = await chain.ainvoke({"test_function_code": code})
```

### 5.3 Benefits of LangChain

✅ **Standardized LLM interface** across providers
✅ **Built-in retry logic** with exponential backoff
✅ **Automatic token counting** via callbacks
✅ **Prompt versioning** and management
✅ **Type-safe output parsing** with Pydantic
✅ **Async-first design** for performance

---

## 6. DeepSeek LLM Configuration

### 6.1 Model Selection

**Primary Model:** `deepseek-chat`
- **Context window:** 64K tokens
- **Cost:** ~$0.14/1M input tokens, ~$0.28/1M output tokens
- **Latency:** 500-1500ms average
- **Quality:** Comparable to GPT-3.5-turbo

### 6.2 Environment Configuration

**Environment Variables (NOT committed to Git):**
```bash
# .env (gitignored)
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=sk-*****  # Actual key stored securely
```

**Environment Template (committed to Git):**
```bash
# .env.example
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=your_api_key_here
```

### 6.3 Security Measures

✅ `.env` is in `.gitignore`
✅ API keys loaded via `pydantic-settings`
✅ Secrets never logged or exposed in errors
✅ Optional key rotation support
✅ Rate limiting to prevent abuse

**Configuration Class:**
```python
from pydantic_settings import BaseSettings

class LLMSettings(BaseSettings):
    deepseek_base_url: str
    deepseek_api_key: str
    deepseek_model: str = "deepseek-chat"
    deepseek_temperature: float = 0.1
    deepseek_max_tokens: int = 2000
    deepseek_timeout: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### 6.4 Rate Limiting

**Strategy:** Token bucket algorithm
- **Limit:** 100 requests/minute
- **Burst:** 10 concurrent requests
- **Retry:** Exponential backoff (2s, 4s, 8s)

---

## 7. Quality Gates

### 7.1 Quality Gate Pattern

Each agent implements two validation methods:

```python
async def validate_input(self, context: AgentContext) -> List[str]:
    """
    Pre-execution validation.

    Returns:
        List of error messages (empty if valid)
    """

async def validate_output(self, result: AgentResult, context: AgentContext) -> List[str]:
    """
    Post-execution validation.

    Returns:
        List of error messages (empty if valid)
    """
```

### 7.2 Agent-Specific Gates

#### InputProcessingAgent
- **Input:** Request schema, file sizes
- **Output:** Sanitized content, no PII detected

#### StrategyPlanningAgent
- **Input:** Valid mode selection
- **Output:** Complete execution plan

#### ParsingAgent
- **Input:** Valid Python syntax (lenient)
- **Output:** Non-empty AST, all functions extracted

#### RuleAnalysisAgent
- **Input:** Parsed files available
- **Output:** Issues have file/line/type

#### LLMAnalysisAgent
- **Input:** Valid prompts, API key present
- **Output:** Valid JSON, confidence > threshold

#### SynthesisAgent
- **Input:** At least one issue source
- **Output:** No duplicate issues

#### EnhancementAgent
- **Input:** Issues present
- **Output:** All issues have suggestions

#### QualityAssuranceAgent
- **Input:** Complete pipeline results
- **Output:** Response matches schema

---

## 8. Performance Optimization

### 8.1 Parallel Execution

**Layer 3 agents run concurrently:**
```python
async def execute_parallel_analysis(context: AgentContext):
    tasks = [
        parsing_agent.run(context),
        rule_agent.run(context) if mode in ['rules-only', 'hybrid'] else None,
        llm_agent.run(context) if mode in ['llm-only', 'hybrid'] else None,
    ]
    results = await asyncio.gather(*[t for t in tasks if t is not None])
```

**Expected speedup:**
- **Sequential:** 10-15s (parse 2s + rules 1s + llm 8s)
- **Parallel:** 6-10s (max(parse, rules, llm) = 8s)
- **Improvement:** 40% faster

### 8.2 Caching Strategy

**Parse Cache:**
- **Key:** `hash(file_path + content)`
- **TTL:** 5 minutes
- **Storage:** In-memory LRU (1000 entries)

**LLM Response Cache:**
- **Key:** `hash(prompt + model + temperature)`
- **TTL:** 1 hour
- **Storage:** Redis (optional) or in-memory

### 8.3 Batching

**LLM requests batched:**
- **Batch size:** 5 test functions per request
- **Benefit:** Reduce API calls by 80%

---

## 9. Security Considerations

### 9.1 API Key Management

❌ **Never do:**
- Commit `.env` to Git
- Log API keys
- Expose keys in error messages
- Hardcode keys in source

✅ **Always do:**
- Use environment variables
- Validate keys on startup
- Rotate keys periodically
- Use separate keys for dev/prod

### 9.2 Input Sanitization

**Prevent:**
- Code injection in file content
- XXE attacks in XML configs
- Path traversal in file paths

**Implementation:**
```python
def sanitize_file_path(path: str) -> str:
    """Remove path traversal attempts."""
    return path.replace("..", "").replace("~", "")
```

### 9.3 Rate Limiting

**Protect against:**
- API abuse
- Cost overruns
- DDoS attacks

**Limits:**
- 100 requests/minute per IP
- 1000 files per request max
- 10MB total request size

---

## 10. Implementation Phases

### Phase 1: Core Infrastructure (2-3 days)
**Deliverables:**
- `BaseAgent` abstract class
- `AgentContext` data class
- `AgentOrchestrator` pipeline manager
- `AgentResult` standardized output
- DeepSeek LLM client setup
- Unit tests (>90% coverage)

**Files created:**
```
app/agents/
├── __init__.py
├── base.py                 # BaseAgent
├── context.py              # AgentContext, AgentResult
├── orchestrator.py         # AgentOrchestrator
└── llm/
    ├── __init__.py
    ├── client.py           # DeepSeek LangChain client
    └── settings.py         # LLMSettings
```

### Phase 2: Core Analysis Agents (3-4 days)
**Deliverables:**
- InputProcessingAgent
- StrategyPlanningAgent
- ParsingAgent
- RuleAnalysisAgent
- LLMAnalysisAgent
- SynthesisAgent
- Integration tests

**Files created:**
```
app/agents/
├── input_processing.py
├── strategy_planning.py
├── parsing.py
├── rule_analysis.py
├── llm_analysis.py
└── synthesis.py
```

### Phase 3: Enhancement & QA (2-3 days)
**Deliverables:**
- EnhancementAgent
- QualityAssuranceAgent
- End-to-end tests
- Performance benchmarks

**Files created:**
```
app/agents/
├── enhancement.py
└── quality_assurance.py
```

### Phase 4: Monitoring & Production (1-2 days)
**Deliverables:**
- Metrics collection
- Logging setup
- Cache implementation
- Production deployment guide

**Files created:**
```
app/agents/
├── monitoring.py
└── cache.py
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

**Coverage target:** >90%

**Test categories:**
- Agent input validation
- Agent output validation
- Error handling
- Metric collection

**Example:**
```python
@pytest.mark.asyncio
async def test_base_agent_validates_input():
    agent = ConcreteAgent()
    context = AgentContext(...)

    # Inject invalid data
    context.files = []

    result = await agent.run(context)
    assert not result.success
    assert "No files provided" in result.errors
```

### 11.2 Integration Tests

**Coverage:** Agent interactions

**Scenarios:**
- Sequential pipeline execution
- Parallel agent coordination
- Error propagation
- Context sharing

### 11.3 Performance Tests

**Metrics:**
- Response time (p50, p95, p99)
- Throughput (requests/second)
- Memory usage
- API call count

**Benchmarks:**
```python
@pytest.mark.benchmark
def test_hybrid_mode_performance(benchmark):
    result = benchmark(run_analysis, files=sample_files, mode="hybrid")
    assert result.metrics.analysis_time_ms < 10000  # 10s max
```

### 11.4 LLM Evaluation Tests

**Use existing evaluation framework:**
- Assertion quality evaluation
- Test smell detection accuracy
- False positive rate
- Suggestion quality

---

## 12. Monitoring and Observability

### 12.1 Metrics Collected

**Agent-level:**
- Execution count
- Success rate
- Average execution time
- Error count

**Pipeline-level:**
- End-to-end latency
- Agent contribution (% of total time)
- Cache hit rate
- API call count

### 12.2 Logging

**Log levels:**
- `DEBUG`: Agent state transitions
- `INFO`: Pipeline milestones
- `WARNING`: Validation failures
- `ERROR`: Exceptions

**Structured logging:**
```python
logger.info(
    "Agent completed",
    extra={
        "agent_name": self.name,
        "execution_time_ms": execution_time,
        "success": result.success,
        "request_id": context.request_id,
    }
)
```

### 12.3 Alerts

**Critical alerts:**
- API key invalid/expired
- Error rate > 5%
- Latency p95 > 15s
- Cache size > 80% capacity

---

## 13. Migration Strategy

### 13.1 Backward Compatibility

**Ensure existing API contract unchanged:**
- Same request/response schemas
- Same endpoint URLs
- Same error codes

**Implementation:**
- Keep old `TestAnalyzer` as fallback
- Feature flag for agent framework
- Gradual rollout (10% → 50% → 100%)

### 13.2 Rollout Plan

**Week 1:**
- Deploy with feature flag OFF
- Run shadow mode (dual execution)
- Compare results

**Week 2:**
- Enable for 10% of traffic
- Monitor metrics
- Fix issues

**Week 3:**
- Ramp to 50%
- Performance tuning
- Cache optimization

**Week 4:**
- Full rollout to 100%
- Deprecate old analyzer
- Update documentation

---

## 14. Future Enhancements

### 14.1 Short-term (Next Sprint)
- Redis cache backend
- Custom rule plugins
- Streaming responses

### 14.2 Medium-term (Next Quarter)
- Multi-model support (GPT-4, Claude)
- Auto-fix code generation
- GitHub integration

### 14.3 Long-term (Future)
- Agent learning from feedback
- Custom agent marketplace
- Real-time analysis in IDE

---

## Appendix A: Code Examples

### Example 1: Simple Agent Implementation

```python
from app.agents.base import BaseAgent, AgentResult
from app.agents.context import AgentContext

class ExampleAgent(BaseAgent):
    """Example agent demonstrating the pattern."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Process files and return result."""
        try:
            # Your logic here
            processed_data = self._process(context.files)

            return AgentResult(
                success=True,
                data=processed_data,
                errors=[],
                warnings=[],
                metadata={"agent": self.name},
                execution_time_ms=0  # Will be set by run()
            )
        except Exception as e:
            return AgentResult(
                success=False,
                data=None,
                errors=[str(e)],
                warnings=[],
                metadata={"agent": self.name},
                execution_time_ms=0
            )

    async def validate_input(self, context: AgentContext) -> list[str]:
        """Validate input before processing."""
        errors = []
        if not context.files:
            errors.append("No files provided")
        return errors
```

---

## Appendix B: Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_BASE_URL` | Yes | - | DeepSeek API endpoint |
| `DEEPSEEK_API_KEY` | Yes | - | DeepSeek API key |
| `DEEPSEEK_MODEL` | No | `deepseek-chat` | Model name |
| `DEEPSEEK_TEMPERATURE` | No | `0.1` | LLM temperature |
| `DEEPSEEK_MAX_TOKENS` | No | `2000` | Max response tokens |
| `DEEPSEEK_TIMEOUT` | No | `30` | Request timeout (seconds) |
| `ENABLE_AGENT_FRAMEWORK` | No | `false` | Feature flag |
| `AGENT_CACHE_TTL` | No | `300` | Cache TTL (seconds) |
| `AGENT_MAX_RETRIES` | No | `3` | Max retry attempts |

---

## Appendix C: Glossary

- **Agent:** Self-contained processing unit with specific responsibility
- **Context:** Shared state passed between agents
- **Orchestrator:** Pipeline manager coordinating agent execution
- **Quality Gate:** Validation checkpoint before/after agent execution
- **Synthesis:** Merging results from multiple agents
- **Enhancement:** Adding suggestions and metadata to issues

---

**Document End**
