#!/usr/bin/env timeguard-python
# =============================================================================
# FILE PURPOSE:
# Demonstrates how to enforce function-level SLA execution limits using the
# '@time_guarded(ms=...)' decorator from the 'timeguard' SDK.
#
# -----------------------------------------------------------------------------
# 🔴 TEST 1: RUN WITH NORMAL PYTHON
# -----------------------------------------------------------------------------
# Command:
#   wsl python3 examples/03_function_decorator.py
#   (or: python examples/03_function_decorator.py)
#
# Expected Output:
#   ============================================================
#   Example 3: Function SLA Enforcement via Decorator
#   ============================================================
#   [Run 1] Normal search (should succeed):
#   Traceback (most recent call last):
#     ...
#   RuntimeError: TimeGuard-PVM is not supported on this interpreter.
#   Please run your script using 'timeguard-python'.
#
# Explanation:
#   The '@time_guarded' decorator checks for runtime support. When executed on
#   unmodified Python, it warns that the VM has no internal deadline engine.
#
# -----------------------------------------------------------------------------
# 🟢 TEST 2: RUN WITH TIMEGUARD-PVM
# -----------------------------------------------------------------------------
# Command:
#   wsl timeguard-python examples/03_function_decorator.py
#
# Expected Output:
#   ============================================================
#   Example 3: Function SLA Enforcement via Decorator
#   ============================================================
#   [Run 1] Normal search (should succeed):
#   Starting graph search (size=50000, hang=False)...
#   Success! Visited 50000 nodes.
#
#   [Run 2] Cyclical search (should trigger TimeGuard):
#   Starting graph search (size=50000, hang=True)...
#   [INTERRUPTED] Function aborted after 199.19 ms
#   Reason: TimeGuard-PVM: execution time budget exceeded
#
# Explanation:
#   Run 1 finishes in ~3ms. Run 2 gets trapped in a simulated infinite graph
#   cycle and is terminated by TimeGuard at the 200ms mark, allowing the program
#   to handle the SLA failure gracefully.
# =============================================================================

import os
import sys
import time

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from timeguard import time_guarded

# Protect this search function with a strict 200ms SLA
@time_guarded(ms=200)
def search_in_graph(graph_size: int, force_hang: bool = False):
    """Simulates a complex graph search algorithm."""
    start = time.monotonic()
    print(f"Starting graph search (size={graph_size}, hang={force_hang})...")
    
    if force_hang:
        # Simulates getting trapped in a cyclical loop
        while True:
            pass
            
    # Normal computation that finishes quickly
    visited = 0
    for node in range(graph_size):
        visited += 1
    return visited

def main():
    print("=" * 60)
    print("Example 3: Function SLA Enforcement via Decorator")
    print("=" * 60)

    # 1. Normal call that finishes within budget
    print("\n[Run 1] Normal search (should succeed):")
    nodes = search_in_graph(50_000, force_hang=False)
    print(f"Success! Visited {nodes} nodes.")

    # 2. Pathological call that hangs (should be aborted at ~200ms)
    print("\n[Run 2] Cyclical search (should trigger TimeGuard):")
    t0 = time.monotonic()
    try:
        search_in_graph(50_000, force_hang=True)
    except RuntimeError as err:
        elapsed = (time.monotonic() - t0) * 1000.0
        print(f"[INTERRUPTED] Function aborted after {elapsed:.2f} ms")
        print(f"Reason: {err}")

if __name__ == "__main__":
    main()
