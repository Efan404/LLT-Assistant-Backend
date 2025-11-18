"""
JSON schema validators for LLM output validation.

Ensures LLM outputs conform to expected JSON structure for each analysis type.
"""

from typing import Any, Dict, List, Optional, Tuple


class JSONSchemaValidator:
    """Validates JSON structure of LLM outputs."""

    @staticmethod
    def validate_mergeability_output(
        output: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate mergeability analysis output schema.

        Expected schema:
        {
            "mergeable": bool,
            "confidence": float (0.0-1.0),
            "reason": str,
            "merged_test_name": str | null,
            "concerns": List[str]
        }

        Args:
            output: LLM output to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["mergeable", "confidence", "reason", "concerns"]

        for field in required_fields:
            if field not in output:
                return False, f"Missing required field: {field}"

        if not isinstance(output["mergeable"], bool):
            return (
                False,
                f"Field 'mergeable' must be boolean, got {type(output['mergeable'])}",
            )

        if not isinstance(output["confidence"], (int, float)):
            return (
                False,
                f"Field 'confidence' must be numeric, got {type(output['confidence'])}",
            )

        if not (0.0 <= output["confidence"] <= 1.0):
            return (
                False,
                f"Field 'confidence' must be between 0.0 and 1.0, got {output['confidence']}",
            )

        if not isinstance(output["reason"], str):
            return False, f"Field 'reason' must be string, got {type(output['reason'])}"

        if not isinstance(output["concerns"], list):
            return (
                False,
                f"Field 'concerns' must be list, got {type(output['concerns'])}",
            )

        if "merged_test_name" in output:
            if output["merged_test_name"] is not None and not isinstance(
                output["merged_test_name"], str
            ):
                return (
                    False,
                    f"Field 'merged_test_name' must be string or null, got {type(output['merged_test_name'])}",
                )

        return True, None

    @staticmethod
    def validate_assertion_quality_output(
        output: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate assertion quality analysis output schema.

        Expected schema:
        {
            "issues": List[{
                "type": str,
                "line": int,
                "severity": str,
                "description": str,
                "suggestion": str
            }],
            "overall_quality": str,
            "confidence": float (0.0-1.0)
        }

        Args:
            output: LLM output to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["issues", "overall_quality", "confidence"]

        for field in required_fields:
            if field not in output:
                return False, f"Missing required field: {field}"

        if not isinstance(output["issues"], list):
            return False, f"Field 'issues' must be list, got {type(output['issues'])}"

        for idx, issue in enumerate(output["issues"]):
            if not isinstance(issue, dict):
                return False, f"Issue at index {idx} must be dict, got {type(issue)}"

            issue_required = ["type", "severity", "description", "suggestion"]
            for issue_field in issue_required:
                if issue_field not in issue:
                    return False, f"Issue at index {idx} missing field: {issue_field}"

            if "line" in issue and not isinstance(issue["line"], int):
                return (
                    False,
                    f"Issue at index {idx}: 'line' must be int, got {type(issue['line'])}",
                )

        if not isinstance(output["overall_quality"], str):
            return (
                False,
                f"Field 'overall_quality' must be string, got {type(output['overall_quality'])}",
            )

        valid_qualities = ["poor", "fair", "good", "excellent"]
        if output["overall_quality"] not in valid_qualities:
            return (
                False,
                f"Field 'overall_quality' must be one of {valid_qualities}, got '{output['overall_quality']}'",
            )

        if not isinstance(output["confidence"], (int, float)):
            return (
                False,
                f"Field 'confidence' must be numeric, got {type(output['confidence'])}",
            )

        if not (0.0 <= output["confidence"] <= 1.0):
            return (
                False,
                f"Field 'confidence' must be between 0.0 and 1.0, got {output['confidence']}",
            )

        return True, None

    @staticmethod
    def validate_test_smell_output(
        output: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate test smell detection output schema.

        Expected schema:
        {
            "smells": List[{
                "type": str,
                "line": int,
                "severity": str,
                "description": str,
                "suggestion": str
            }],
            "confidence": float (0.0-1.0)
        }

        Args:
            output: LLM output to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["smells", "confidence"]

        for field in required_fields:
            if field not in output:
                return False, f"Missing required field: {field}"

        if not isinstance(output["smells"], list):
            return False, f"Field 'smells' must be list, got {type(output['smells'])}"

        for idx, smell in enumerate(output["smells"]):
            if not isinstance(smell, dict):
                return False, f"Smell at index {idx} must be dict, got {type(smell)}"

            smell_required = ["type", "severity", "description", "suggestion"]
            for smell_field in smell_required:
                if smell_field not in smell:
                    return False, f"Smell at index {idx} missing field: {smell_field}"

            if "line" in smell and not isinstance(smell["line"], int):
                return (
                    False,
                    f"Smell at index {idx}: 'line' must be int, got {type(smell['line'])}",
                )

            valid_severities = ["info", "warning", "error"]
            if smell["severity"] not in valid_severities:
                return (
                    False,
                    f"Smell at index {idx}: 'severity' must be one of {valid_severities}, got '{smell['severity']}'",
                )

        if not isinstance(output["confidence"], (int, float)):
            return (
                False,
                f"Field 'confidence' must be numeric, got {type(output['confidence'])}",
            )

        if not (0.0 <= output["confidence"] <= 1.0):
            return (
                False,
                f"Field 'confidence' must be between 0.0 and 1.0, got {output['confidence']}",
            )

        return True, None

    @staticmethod
    def validate_all_outputs(
        mergeability_outputs: Optional[List[Dict[str, Any]]] = None,
        assertion_outputs: Optional[List[Dict[str, Any]]] = None,
        smell_outputs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Validate multiple LLM outputs and return comprehensive results.

        Args:
            mergeability_outputs: List of mergeability analysis outputs
            assertion_outputs: List of assertion quality outputs
            smell_outputs: List of test smell outputs

        Returns:
            Dictionary with validation results for each category
        """
        results = {
            "mergeability": {"valid_count": 0, "invalid_count": 0, "errors": []},
            "assertion_quality": {"valid_count": 0, "invalid_count": 0, "errors": []},
            "test_smells": {"valid_count": 0, "invalid_count": 0, "errors": []},
        }

        if mergeability_outputs:
            for idx, output in enumerate(mergeability_outputs):
                is_valid, error = JSONSchemaValidator.validate_mergeability_output(
                    output
                )
                if is_valid:
                    results["mergeability"]["valid_count"] += 1
                else:
                    results["mergeability"]["invalid_count"] += 1
                    results["mergeability"]["errors"].append(
                        {"index": idx, "error": error}
                    )

        if assertion_outputs:
            for idx, output in enumerate(assertion_outputs):
                is_valid, error = JSONSchemaValidator.validate_assertion_quality_output(
                    output
                )
                if is_valid:
                    results["assertion_quality"]["valid_count"] += 1
                else:
                    results["assertion_quality"]["invalid_count"] += 1
                    results["assertion_quality"]["errors"].append(
                        {"index": idx, "error": error}
                    )

        if smell_outputs:
            for idx, output in enumerate(smell_outputs):
                is_valid, error = JSONSchemaValidator.validate_test_smell_output(output)
                if is_valid:
                    results["test_smells"]["valid_count"] += 1
                else:
                    results["test_smells"]["invalid_count"] += 1
                    results["test_smells"]["errors"].append(
                        {"index": idx, "error": error}
                    )

        for category in results:
            total = (
                results[category]["valid_count"] + results[category]["invalid_count"]
            )
            results[category]["total"] = total
            results[category]["validity_rate"] = (
                (results[category]["valid_count"] / total * 100) if total > 0 else 0.0
            )

        return results
