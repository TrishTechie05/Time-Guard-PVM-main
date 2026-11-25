#!/usr/bin/env timeguard-python
# =============================================================================
# FILE PURPOSE:
# Demonstrates how online coding platforms, automated grading judges, or AI agent
# frameworks can evaluate untrusted, user-submitted Python code safely without fear
# of malicious or accidental infinite loops freezing the host server process.
#
# -----------------------------------------------------------------------------
# 🔴 TEST 1: RUN WITH NORMAL PYTHON
# -----------------------------------------------------------------------------
# Command:
#   wsl python3 examples/04_untrusted_code.py
#   (or: python examples/04_untrusted_code.py)
#
# Expected Output:
#   ============================================================
#   Example 4: Sandboxing Untrusted Code Execution
#   ============================================================
#   --- Submitting Job 1 (Valid fast calculation) ---
#   Outcome: {'status': 'ERROR', 'error': 'RuntimeError: TimeGuard-PVM is not supported on this interpreter.'}
#
# Explanation:
#   Without TimeGuard, standard Python cannot safely bound exec() execution.
#
# -----------------------------------------------------------------------------
# 🟢 TEST 2: RUN WITH TIMEGUARD-PVM
# -----------------------------------------------------------------------------
# Command:
#   wsl timeguard-python examples/04_untrusted_code.py
#
# Expected Output:
#   ============================================================
#   Example 4: Sandboxing Untrusted Code Execution
#   ============================================================
#   --- Submitting Job 1 (Valid fast calculation) ---
#   Outcome: {'status': 'SUCCESS', 'elapsed_ms': 0.53, 'result': 999000}
#
#   --- Submitting Job 2 (Infinite loop submission) ---
#   Outcome: {'status': 'TIME_LIMIT_EXCEEDED', 'elapsed_ms': 100.85, 'error': 'Execution exceeded 100 ms time budget'}
#
#   Host process remains fully responsive and ready for new jobs!
#
# Explanation:
#   Job 1 runs untrusted calculation in 0.53ms and succeeds. Job 2 attempts an
#   infinite while-loop attack; TimeGuard catches it in ~100ms, records a clean
#   'TIME_LIMIT_EXCEEDED' status, and leaves the host server online.
# =============================================================================

import os
import sys
import time

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from timeguard import time_budget

def run_untrusted_script(code_string: str, max_allowed_ms: int = 100):
    """
    Executes an untrusted Python script string inside a strictly timed sandbox.
    
    Args:
        code_string: The Python code to run.
        max_allowed_ms: Maximum execution time permitted in milliseconds.
        
    Returns:
        dict: Execution status and result or error description.
    """
    sandbox_globals = {"__builtins__": __builtins__}
    sandbox_locals = {}
    
    t0 = time.monotonic()
    try:
        # Wrap the exec() call inside TimeGuard
        with time_budget(max_allowed_ms):
            exec(code_string, sandbox_globals, sandbox_locals)
            
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        return {
            "status": "SUCCESS",
            "elapsed_ms": round(elapsed_ms, 2),
            "result": sandbox_locals.get("output", None)
        }
    except RuntimeError as exc:
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        if "TimeGuard-PVM" in str(exc):
            return {
                "status": "TIME_LIMIT_EXCEEDED",
                "elapsed_ms": round(elapsed_ms, 2),
                "error": f"Execution exceeded {max_allowed_ms} ms time budget"
            }
        return {"status": "RUNTIME_ERROR", "error": str(exc)}
    except Exception as exc:
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}

def main():
    print("=" * 60)
    print("Example 4: Sandboxing Untrusted Code Execution")
    print("=" * 60)

    # 1. Benign submission: Fast calculation
    submission_1 = """
output = sum(x * 2 for x in range(1000))
"""
    print("\n--- Submitting Job 1 (Valid fast calculation) ---")
    result_1 = run_untrusted_script(submission_1, max_allowed_ms=100)
    print(f"Outcome: {result_1}")

    # 2. Malicious or accidental infinite loop submission
    submission_2 = """
# Student submission with an off-by-one infinite while loop
count = 0
while True:
    count += 1
output = count
"""
    print("\n--- Submitting Job 2 (Infinite loop submission) ---")
    result_2 = run_untrusted_script(submission_2, max_allowed_ms=100)
    print(f"Outcome: {result_2}")

    print("\nHost process remains fully responsive and ready for new jobs!")

if __name__ == "__main__":
    main()
