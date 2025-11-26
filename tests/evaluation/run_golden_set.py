import os
import json
import glob
import sys
import argparse
import difflib
from typing import Dict, Any, List, Tuple
from jinja2 import Template
import unittest.mock

# Add project root to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from src.agent.main import analyze_contract
except ImportError:
    print("Error: Could not import src.agent.main. Ensure the module exists.")
    sys.exit(1)

# Optional Vertex AI import
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False

CONTRACTS_DIR = os.path.join(os.path.dirname(__file__), "../data/golden_set/contracts")
GROUND_TRUTH_PATH = os.path.join(os.path.dirname(__file__), "../data/golden_set/ground_truth.json")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "report.html")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Golden Set Evaluation Report</title>
    <style>
        body { font-family: sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .pass { background-color: #d4edda; color: #155724; }
        .fail { background-color: #f8d7da; color: #721c24; }
        .summary { font-size: 1.2em; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>Golden Set Evaluation Report</h1>
    <div class="summary">
        <p><strong>Total Tests:</strong> {{ total }}</p>
        <p><strong>Passed:</strong> {{ passed }} ({{ pass_rate }}%)</p>
        <p><strong>Failed:</strong> {{ failed }}</p>
        <p><strong>Accuracy:</strong> {{ accuracy }}%</p>
        <p><strong>Precision:</strong> {{ precision }}</p>
        <p><strong>Recall:</strong> {{ recall }}</p>
    </div>
    
    <table>
        <tr>
            <th>Contract</th>
            <th>Status</th>
            <th>Details</th>
        </tr>
        {% for result in results %}
        <tr class="{{ 'pass' if result.passed else 'fail' }}">
            <td>{{ result.filename }}</td>
            <td>{{ 'PASS' if result.passed else 'FAIL' }}</td>
            <td>
                {% if not result.passed %}
                <ul>
                    {% for diff in result.diffs %}
                    <li>{{ diff }}</li>
                    {% endfor %}
                </ul>
                {% else %}
                All checks passed.
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

def semantic_similarity(text1: str, text2: str, use_llm: bool = False) -> float:
    """
    Calculates semantic similarity between two text strings.
    """
    if not text1 or not text2:
        return 0.0 if text1 != text2 else 1.0
        
    # 1. Heuristic Check using SequenceMatcher
    matcher = difflib.SequenceMatcher(None, str(text1), str(text2))
    ratio = matcher.ratio()
    
    if ratio > 0.8:
        return ratio

    # 2. Vertex AI Check (Bonus)
    if use_llm and VERTEX_AVAILABLE:
        try:
            model = GenerativeModel("gemini-1.5-flash")
            prompt = f"Do these two explanations mean the same thing? Yes/No.\n\nExplanation 1: {text1}\nExplanation 2: {text2}"
            response = model.generate_content(prompt)
            if "yes" in response.text.lower():
                return 1.0
        except Exception as e:
            print(f"Warning: Vertex AI semantic check failed: {e}")
            
    return ratio

def compare_result(actual: Dict[str, Any], expected: Dict[str, Any], use_llm: bool = False) -> Tuple[bool, List[str]]:
    """
    Compares actual result with expected ground truth.
    Returns (Passed (bool), List of diff strings).
    """
    passed = True
    diffs = []
    
    # Check boolean fields strictly
    for key in ["is_safe", "has_indemnity"]:
        if key in expected:
            if actual.get(key) != expected[key]:
                passed = False
                diffs.append(f"Field '{key}': Expected {expected[key]}, got {actual.get(key)}")

    # Check numeric fields with tolerance
    if "risk_score" in expected:
        actual_score = actual.get("risk_score", 0.0)
        expected_score = expected["risk_score"]
        if abs(actual_score - expected_score) > 0.1:
            passed = False
            diffs.append(f"Field 'risk_score': Expected {expected_score}, got {actual_score}")

    # Check text fields with fuzzy matching
    for key in ["summary", "reasoning"]:
        if key in expected:
            actual_text = str(actual.get(key, ""))
            expected_text = str(expected[key])
            similarity = semantic_similarity(actual_text, expected_text, use_llm)
            if similarity < 0.8:
                passed = False
                diffs.append(f"Field '{key}': Low similarity ({similarity:.2f}). Expected: '{expected_text}', Got: '{actual_text}'")
                
    return passed, diffs

def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculates Precision, Recall, and Accuracy based on 'is_safe' classification.
    Note: This assumes binary classification where 'is_safe=False' is Positive (Risky) detection?
    Usually:
      - True Positive (TP): Predicted Risky (Unsafe), Actual Risky (Unsafe)
      - True Negative (TN): Predicted Safe, Actual Safe
      - False Positive (FP): Predicted Risky, Actual Safe
      - False Negative (FN): Predicted Safe, Actual Risky
    
    Let's assume the goal is detecting RISKY contracts.
    Class 1: Risky (is_safe=False)
    Class 0: Safe (is_safe=True)
    """
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    total = 0
    matches = 0
    
    for res in results:
        total += 1
        # We need expected and actual is_safe to calc metrics
        # Assuming result object has these stashed or we pass them.
        # Let's store them in the result dict passed to this function.
        
        actual_safe = res["actual_is_safe"]
        expected_safe = res["expected_is_safe"]
        
        if res["passed"]:
            matches += 1
            
        # Logic for Classification Metrics (Risk Detection)
        actual_risky = not actual_safe
        expected_risky = not expected_safe
        
        if actual_risky and expected_risky:
            tp += 1
        elif not actual_risky and not expected_risky:
            tn += 1
        elif actual_risky and not expected_risky:
            fp += 1
        elif not actual_risky and expected_risky:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    accuracy_classification = (tp + tn) / total if total > 0 else 0.0
    
    # "Overall Accuracy" for the exit code usually refers to "Test Pass Rate" in QA contexts,
    # i.e., how many test cases fully matched expectations (including text fields).
    # But the requirements say "Calculate Precision, Recall, and Overall Accuracy".
    # And "If Overall Accuracy >= 95%: Exit code 0".
    # If we use classification accuracy, text diffs don't count? 
    # The requirement: "Compare actual vs expected... Calculate... Accuracy".
    # Then: "If Overall Accuracy >= 95%".
    # And "Print summary: PASS: 48/50 tests (96%)".
    # This phrasing "48/50 tests" strongly implies the Test Pass Rate (matches / total).
    
    test_pass_rate = (matches / total) * 100 if total > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "accuracy_classification": accuracy_classification,
        "pass_rate": test_pass_rate,
        "passed_count": matches,
        "total_count": total
    }

def main():
    parser = argparse.ArgumentParser(description="Run Golden Set Evaluation")
    parser.add_argument("--use-llm", action="store_true", help="Use Vertex AI for semantic comparison")
    args = parser.parse_args()

    # Load Ground Truth
    if not os.path.exists(GROUND_TRUTH_PATH):
        print(f"Error: Ground truth file not found at {GROUND_TRUTH_PATH}")
        sys.exit(1)

    with open(GROUND_TRUTH_PATH, 'r') as f:
        ground_truth = json.load(f)

    results = []

    # Find Contracts
    contract_files = glob.glob(os.path.join(CONTRACTS_DIR, "*.txt"))
    if not contract_files:
        print(f"Error: No contract files found in {CONTRACTS_DIR}")
        sys.exit(1)

    print(f"Found {len(contract_files)} contracts. Running evaluation...")

    # Mocking DB calls globally if needed (The agent mock I wrote doesn't use DB, but for safety in real env)
    with unittest.mock.patch('src.core.firestore_wrapper.TenantFirestore') as MockDB:
        for contract_path in contract_files:
            filename = os.path.basename(contract_path)
            
            if filename not in ground_truth:
                print(f"Warning: No ground truth for {filename}, skipping.")
                continue
                
            expected = ground_truth[filename]
            
            with open(contract_path, 'r') as f:
                text = f.read()
            
            try:
                actual = analyze_contract(text)
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                results.append({
                    "filename": filename,
                    "passed": False,
                    "diffs": [f"Exception: {str(e)}"],
                    "actual_is_safe": False, # Default fallback
                    "expected_is_safe": expected.get("is_safe", False)
                })
                continue

            passed, diffs = compare_result(actual, expected, use_llm=args.use_llm)
            
            results.append({
                "filename": filename,
                "passed": passed,
                "diffs": diffs,
                "actual_is_safe": actual.get("is_safe"),
                "expected_is_safe": expected.get("is_safe")
            })

    # Calculate Metrics
    metrics = calculate_metrics(results)
    
    # Render Report
    template = Template(HTML_TEMPLATE)
    html_content = template.render(
        results=results,
        total=metrics["total_count"],
        passed=metrics["passed_count"],
        failed=metrics["total_count"] - metrics["passed_count"],
        pass_rate=f"{metrics['pass_rate']:.1f}",
        accuracy=f"{metrics['accuracy_classification']*100:.1f}",
        precision=f"{metrics['precision']:.2f}",
        recall=f"{metrics['recall']:.2f}"
    )
    
    with open(REPORT_PATH, 'w') as f:
        f.write(html_content)
        
    print(f"Report generated at {REPORT_PATH}")
    
    # Console Summary
    print(f"PASS: {metrics['passed_count']}/{metrics['total_count']} tests ({metrics['pass_rate']:.1f}%)")
    print(f"Classification Metrics - Accuracy: {metrics['accuracy_classification']:.2f}, Precision: {metrics['precision']:.2f}, Recall: {metrics['recall']:.2f}")

    # Exit Code Strategy
    # Requirement: If Overall Accuracy >= 95%: Exit code 0.
    # Assuming "Overall Accuracy" refers to the Test Pass Rate based on the console message format requirement.
    if metrics['pass_rate'] >= 95.0:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
