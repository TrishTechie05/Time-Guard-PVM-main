#!/usr/bin/env timeguard-python
# =============================================================================
# FILE PURPOSE:
# Demonstrates how to use the 'with time_budget(ms):' context manager from the
# 'timeguard' SDK to protect a block of code with an execution deadline.
#
# -----------------------------------------------------------------------------
# 🔴 TEST 1: RUN WITH NORMAL PYTHON
# -----------------------------------------------------------------------------
# Command:
#   wsl python3 examples/02_context_manager.py
#   (or: python examples/02_context_manager.py)
#
# Expected Output:
#   ============================================================
#   Example 2: Using the 'time_budget' Context Manager
#   ============================================================
#   --- Task 1: Fast calculation within 500ms budget ---
#   Traceback (most recent call last):
#     ...
#   RuntimeError: TimeGuard-PVM is not supported on this interpreter.
#   Please run your script using 'timeguard-python'.
#
# Explanation:
#   The TimeGuard SDK detects that the underlying Python interpreter has no
#   virtual machine time-guard capabilities, raising an informative RuntimeError.
#
# -----------------------------------------------------------------------------
# 🟢 TEST 2: RUN WITH TIMEGUARD-PVM
# -----------------------------------------------------------------------------
# Command:
#   wsl timeguard-python examples/02_context_manager.py
#
# Expected Output:
#   ============================================================
#   Example 2: Using the 'time_budget' Context Manager
#   ============================================================
#   --- Task 1: Fast calculation within 500ms budget ---
#   Task 1 completed successfully! Result: 41665416675000
#
#   --- Task 2: Accidental infinite loop bounded to 100ms ---
#   Entering protected block with 100ms limit...
#   [CAUGHT] TimeGuard-PVM: execution time budget exceeded
#   Context manager interrupted loop after 100.10 ms
#
#   Execution continues outside the context manager.
#
# Explanation:
#   Task 1 finishes in ~5ms without hindrance. Task 2's infinite while loop is
#   halted by the PVM in ~100ms, and execution resumes smoothly afterward.
# =============================================================================

import os
import sys
import time

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from timeguard import time_budget

def main():
    print("=" * 60)
    print("Example 2: Using the 'time_budget' Context Manager")
    print("=" * 60)

    # Fast task within budget
    print("\n--- Task 1: Fast calculation within 500ms budget ---")
    with time_budget(500):
        # This completes in ~5ms, well under the 500ms budget
        result = sum(x * x for x in range(50_000))
        print(f"Task 1 completed successfully! Result: {result}")

    # Slow or runaway task exceeding budget
    print("\n--- Task 2: Accidental infinite loop bounded to 100ms ---")
    start = time.monotonic()
    try:
        with time_budget(100):
            print("Entering protected block with 100ms limit...")
            while True:
                # Simulating a stalled calculation or infinite recursion
                pass
    except RuntimeError as exc:
        elapsed = (time.monotonic() - start) * 1000.0
        print(f"[CAUGHT] {exc}")
        print(f"Context manager interrupted loop after {elapsed:.2f} ms")

    print("\nExecution continues outside the context manager.")

if __name__ == "__main__":
    main()
