import time
from typing import Dict, Any

def analyze_contract(text: str) -> Dict[str, Any]:
    """
    Mock implementation of the agent's main analysis function.
    In a real scenario, this would use LLMs and Firestore.
    """
    # Simulate processing time
    time.sleep(0.1)
    
    # Simple deterministic mock based on content keywords
    is_safe = "indemnify" not in text.lower() and "terminate" not in text.lower()
    
    return {
        "is_safe": is_safe,
        "risk_score": 0.1 if is_safe else 0.9,
        "summary": f"Analyzed contract of length {len(text)}.",
        "reasoning": "No risky clauses found." if is_safe else "Found risky clauses.",
        "has_indemnity": "indemnify" in text.lower()
    }
