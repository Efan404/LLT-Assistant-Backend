# LLM Evaluation Suite

Comprehensive evaluation framework for measuring the quality and accuracy of LLM-based test analysis in the LLT-Assistant-Backend project.

## Overview

This evaluation suite tests three core LLM analysis capabilities:

1. **Test Mergeability Analysis** - Detecting when two tests can be safely merged
2. **Assertion Quality Analysis** - Identifying weak, missing, or redundant assertions
3. **Test Smell Detection** - Finding code smells in test code

The suite uses ground truth datasets based on real pytest patterns to measure precision, recall, F1-score, and confidence calibration.

---

## Directory Structure

```
tests/evaluation/
├── __init__.py
├── README.md                           # This file
├── conftest.py                         # Shared pytest fixtures
├── fixtures/                           # Ground truth datasets
│   ├── __init__.py
│   ├── ground_truth_mergeability.json       # 35 test pairs (mergeable/not mergeable)
│   ├── ground_truth_assertion_quality.json  # 35 assertion quality test cases
│   └── ground_truth_test_smells.json        # 35 test smell detection cases
├── metrics/                            # Custom evaluation metrics
│   ├── __init__.py
│   ├── custom_metrics.py                    # Precision, recall, F1, calibration
│   └── json_validators.py                   # JSON schema validators
├── reports/                            # Reporting utilities
│   ├── __init__.py
│   └── evaluation_report.py                 # Markdown/JSON report generator
├── test_mergeability_eval.py                # Mergeability evaluation tests
├── test_assertion_quality_eval.py           # Assertion quality evaluation tests
└── test_smell_detection_eval.py             # Test smell evaluation tests
```

---

## Running Evaluation Tests

### Prerequisites

1. **Install dependencies** (including DeepEval and scikit-learn):
   ```bash
   pip install -e ".[dev]"
   ```

2. **Set LLM API key**:
   ```bash
   export LLM_API_KEY="your-api-key-here"
   ```

### Run All Evaluation Tests

```bash
pytest tests/evaluation/ -m llm_evaluation -v
```

### Run Specific Evaluation

**Mergeability only:**
```bash
pytest tests/evaluation/test_mergeability_eval.py -v
```

**Assertion quality only:**
```bash
pytest tests/evaluation/test_assertion_quality_eval.py -v
```

**Test smells only:**
```bash
pytest tests/evaluation/test_smell_detection_eval.py -v
```

### Control Sample Size

By default, evaluation tests use 10 samples for faster runs. Override with:

```bash
export EVALUATION_SAMPLE_SIZE=35
pytest tests/evaluation/ -m llm_evaluation -v
```

### Skip Evaluation Tests

Evaluation tests are automatically skipped if `LLM_API_KEY` is not set or if `SKIP_LLM_TESTS=true`:

```bash
export SKIP_LLM_TESTS=true
pytest tests/
```

---

## Ground Truth Datasets

### Structure

Each ground truth JSON file contains:
- **description**: Dataset purpose
- **version**: Dataset version
- **total_cases**: Number of test cases
- **test_cases**: Array of annotated examples
- **statistics**: Dataset statistics

### Example: Mergeability Ground Truth

```json
{
  "id": "merge_001",
  "test_function_1": "def test_addition():\n    assert 5 + 3 == 8",
  "test_function_2": "def test_addition_positive():\n    result = 5 + 3\n    assert result == 8",
  "expected_output": {
    "mergeable": true,
    "confidence": 0.95,
    "reason": "Both tests verify identical functionality",
    "merged_test_name": "test_addition",
    "concerns": []
  },
  "reasoning": "Tests are redundant, should be merged"
}
```

### Updating Ground Truth

To add new test cases:

1. Edit the JSON file in `tests/evaluation/fixtures/`
2. Follow the existing schema structure
3. Increment `total_cases` counter
4. Update `statistics` section
5. Run evaluation to verify the new cases work

---

## Evaluation Metrics

### Mergeability Analysis

**Target Metrics:**
- Precision: ≥ 0.75
- Recall: ≥ 0.70
- F1-Score: ≥ 0.72
- Accuracy: ≥ 0.75

**Measured:**
- True/False Positives/Negatives
- Confidence calibration (Expected Calibration Error)
- JSON schema compliance (≥ 90%)

### Assertion Quality Analysis

**Target Metrics:**
- Precision: ≥ 0.70
- Recall: ≥ 0.65
- F1-Score: ≥ 0.67
- Quality Label Accuracy: ≥ 0.70

**Measured:**
- Issue detection by type (missing, weak, trivial, redundant)
- Quality label distribution (poor/fair/good/excellent)
- JSON schema compliance (≥ 90%)

### Test Smell Detection

**Target Metrics:**
- Precision: ≥ 0.70
- Recall: ≥ 0.65
- F1-Score: ≥ 0.67

**Measured:**
- Overall smell detection accuracy
- Per-smell-type precision/recall (timing_dependency, hardcoded_credentials, etc.)
- False positive rate on clean code (≤ 0.2)
- JSON schema compliance (≥ 90%)

---

## Understanding Evaluation Results

### Example Output

```
================================================================================
MERGEABILITY ANALYSIS EVALUATION
================================================================================
Total test cases: 10
================================================================================

[1/10] Evaluating merge_001... ✓ (confidence: 0.95)
[2/10] Evaluating merge_002... ✗ (confidence: 0.82)
[3/10] Evaluating merge_003... ✓ (confidence: 0.88)
...

================================================================================
MERGEABILITY EVALUATION RESULTS
================================================================================
Samples evaluated: 10
Precision: 0.8500
Recall: 0.7500
F1-Score: 0.7970
Accuracy: 0.8000

Confusion Matrix:
  True Positives: 6
  False Positives: 1
  False Negatives: 2
  True Negatives: 1

Confidence Calibration:
  Expected Calibration Error: 0.0450
  Bin Accuracies: [0.0, 0.0, 0.75, 0.8333, 0.8571, 0.90]
  Bin Confidences: [0.0, 0.0, 0.65, 0.75, 0.825, 0.925]
  Bin Counts: [0, 0, 4, 3, 2, 1]
================================================================================
```

###  Interpretation

- **✓** = Correct prediction (matches ground truth)
- **✗** = Incorrect prediction
- **Expected Calibration Error (ECE)** = How well confidence scores align with accuracy (lower is better)
- **Bin statistics** = Accuracy and confidence at different confidence thresholds

---

## Custom Metrics

### Precision

```
Precision = True Positives / (True Positives + False Positives)
```

Measures how many of the predicted "positives" (e.g., "mergeable") were actually correct.

### Recall

```
Recall = True Positives / (True Positives + False Negatives)
```

Measures how many of the actual positives were successfully detected.

### F1-Score

```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

Harmonic mean of precision and recall - balanced metric.

### Confidence Calibration

Measures how well the LLM's confidence scores align with actual accuracy. Perfect calibration means:
- When the LLM says 80% confidence, it should be correct 80% of the time.

---

## JSON Schema Validation

All LLM outputs must conform to expected schemas:

### Mergeability Output Schema

```python
{
    "mergeable": bool,
    "confidence": float (0.0-1.0),
    "reason": str,
    "merged_test_name": str | null,
    "concerns": List[str]
}
```

### Assertion Quality Output Schema

```python
{
    "issues": List[{
        "type": str,
        "line": int,
        "severity": str,
        "description": str,
        "suggestion": str
    }],
    "overall_quality": "poor" | "fair" | "good" | "excellent",
    "confidence": float (0.0-1.0)
}
```

### Test Smell Output Schema

```python
{
    "smells": List[{
        "type": str,
        "line": int,
        "severity": "info" | "warning" | "error",
        "description": str,
        "suggestion": str
    }],
    "confidence": float (0.0-1.0)
}
```

---

## Generating Reports

### Markdown Report

```python
from tests.evaluation.reports.evaluation_report import EvaluationReportGenerator

report = EvaluationReportGenerator.generate_markdown_report(
    mergeability_metrics=mergeability_results,
    assertion_metrics=assertion_results,
    smell_metrics=smell_results,
    output_path=Path("evaluation_report.md")
)
print(report)
```

### Save Baseline Metrics

```python
metrics = {
    "mergeability": mergeability_results,
    "assertion_quality": assertion_results,
    "test_smells": smell_results
}

EvaluationReportGenerator.save_baseline_metrics(
    metrics,
    output_path=Path("tests/evaluation/reports/baseline_metrics.json")
)
```

### Compare with Baseline

```python
comparison = EvaluationReportGenerator.compare_with_baseline(
    current_metrics=current_results,
    baseline_path=Path("tests/evaluation/reports/baseline_metrics.json")
)

print(f"Improvements: {len(comparison['improvements'])}")
print(f"Regressions: {len(comparison['regressions'])}")
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run LLM Evaluation Tests
  env:
    LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
    EVALUATION_SAMPLE_SIZE: 10
  run: |
    pytest tests/evaluation/ -m llm_evaluation -v
```

### Weekly Evaluation Job

Run full evaluation (all 35 samples) weekly to track model performance over time:

```yaml
schedule:
  - cron: '0 2 * * 0'  # Sunday at 2 AM
jobs:
  full-evaluation:
    env:
      EVALUATION_SAMPLE_SIZE: 35
    ...
```

---

## Troubleshooting

### Issue: Tests Skip with "LLM API key not available"

**Solution:** Export your API key:
```bash
export LLM_API_KEY="your-key"
```

### Issue: Low Precision/Recall

**Possible causes:**
1. Model prompt needs refinement
2. Ground truth labels may need review
3. Model temperature or parameters need tuning

**Debug:**
- Review individual test cases that failed
- Check if false positives/negatives have a pattern
- Adjust confidence threshold (currently 0.7)

### Issue: JSON Schema Validation Failures

**Solution:**
- Check `app/core/llm_analyzer.py` prompt formatting
- Ensure prompt explicitly requests JSON format
- Add retry logic for malformed responses

---

## Adding New Evaluation Tests

### Step 1: Create Ground Truth

Add cases to `tests/evaluation/fixtures/ground_truth_*.json`

### Step 2: Write Test

```python
@pytest.mark.llm_evaluation
@pytest.mark.requires_api_key
class TestMyNewEvaluation:
    @pytest.mark.asyncio
    async def test_my_analysis(
        self,
        ground_truth_data,
        llm_analyzer_for_eval,
        skip_if_no_api_key
    ):
        # Your evaluation logic
        ...
```

### Step 3: Run and Verify

```bash
pytest tests/evaluation/test_my_new_eval.py -v
```

---

## Best Practices

1. **Update ground truth regularly** as you discover edge cases
2. **Run full evaluation** (35 samples) before major releases
3. **Track metrics over time** to detect model drift
4. **Review false positives/negatives** to improve prompts
5. **Maintain realistic test patterns** from actual pytest code

---

## Dataset Statistics

| Dataset | Total Cases | Positive Cases | Negative Cases |
|---------|-------------|----------------|----------------|
| Mergeability | 35 | 13 (37%) | 22 (63%) |
| Assertion Quality | 35 | Issues in 33 (94%) | Clean: 2 (6%) |
| Test Smells | 35 | Smells in 27 (77%) | Clean: 8 (23%) |

---

## References

- **DeepEval Documentation**: https://docs.confident-ai.com/
- **scikit-learn Metrics**: https://scikit-learn.org/stable/modules/model_evaluation.html
- **Pytest Markers**: https://docs.pytest.org/en/stable/how-to/mark.html

---

**Last Updated:** 2025-11-18
**Version:** 1.0
