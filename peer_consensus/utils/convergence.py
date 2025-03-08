import re

def extract_convergence(response: str) -> float:
    """
    Extracts the convergence percentage from the response text.
    Expects an exact line:
    "I am in agreement with {number}% of the overall opinions given by my peers."
    """
    match = re.search(r"I am in agreement with (\d+(?:\.\d+)?)% of the overall opinions given by my peers\.", response)
    if match:
        return float(match.group(1))
    return 0.0

def check_convergence(latest_responses: dict, threshold: float) -> (bool, float):
    """
    Checks if the average convergence percentage across all latest responses
    meets or exceeds the threshold.
    
    Returns:
        (bool, float): Tuple of (converged, average_convergence)
    """
    total = 0.0
    count = 0
    for model, response in latest_responses.items():
        conv = extract_convergence(response)
        total += conv
        count += 1
    if count == 0:
        return False, 0.0
    avg = total / count
    return (avg >= threshold), avg

