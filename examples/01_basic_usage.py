#!/usr/bin/env timeguard-python
# =============================================================================
# FILE PURPOSE:
# Demonstrates how to use the raw C-level TimeGuard hooks on Python's built-in
# 'sys' module:
#   - sys.set_time_budget_ms(ms)
#   - sys.get_time_budget_ms()
#
# -----------------------------------------------------------------------------
# 🔴 TEST 1: RUN WITH NORMAL PYTHON
# -----------------------------------------------------------------------------
# Command:
#   wsl python3 examples/01_basic_usage.py
#   (or: python examples/01_basic_usage.py)
#
# Expected Output:
#   Traceback (most recent call last):
#     ...
#   AttributeError: module 'sys' has no attribute 'get_time_budget_ms'
#
# Explanation:
#   Normal Python has no execution deadline hooks compiled into 'sys', so
#   calling 'sys.get_time_budget_ms()' fails immediately with an AttributeError.
#
# -----------------------------------------------------------------------------
# 🟢 TEST 2: RUN WITH TIMEGUARD-PVM
# -----------------------------------------------------------------------------
# Command:
#   wsl timeguard-python examples/01_basic_usage.py
#
# Expected Output:
#   ============================================================
#   Example 1: Low-Level sys Module TimeGuard API
#   ============================================================
#   Current initial budget: 0 ms
#
#   Arming PVM execution deadline with 150 ms...
#   Active budget: 150 ms
#
#   Entering 'while True:' loop...
#
#   [STOPPED] Execution halted cleanly by Python Virtual Machine!
#     -> Elapsed wall-clock time: 149.03 ms
#     -> Exception caught:        TimeGuard-PVM: execution time budget exceeded
#
#   Budget status after abort: 0 ms (disarmed)
#   Program continues executing normally without hanging or crashing.
# =============================================================================

import sys
import time

def main():
    print("=" * 60)
    print("Example 1: Low-Level sys Module TimeGuard API")
    print("=" * 60)

    # 1. Inspect current execution budget (default is 0 = unlimited)
    print(f"Current initial budget: {sys.get_time_budget_ms()} ms")

    # 2. Configure a 150-millisecond execution deadline
    budget_ms = 150
    print(f"\nArming PVM execution deadline with {budget_ms} ms...")
    sys.set_time_budget_ms(budget_ms)
    print(f"Active budget: {sys.get_time_budget_ms()} ms")

    # 3. Enter a loop that would run forever without TimeGuard
    start_time = time.monotonic()
    try:
        print("\nEntering 'while True:' loop...")
        counter = 0
        while True:
            counter += 1
            # Pure computational loop with no I/O
            pass

    except RuntimeError as error:
        # The PVM cleanly intercepts the loop when elapsed >= budget_ms
        elapsed = (time.monotonic() - start_time) * 1000.0
        print("\n[STOPPED] Execution halted cleanly by Python Virtual Machine!")
        print(f"  -> Elapsed wall-clock time: {elapsed:.2f} ms")
        print(f"  -> Exception caught:        {error}")

    # 4. Demonstrate that normal execution resumes cleanly
    # (The PVM automatically disarms the deadline once exceeded)
    print(f"\nBudget status after abort: {sys.get_time_budget_ms()} ms (disarmed)")
    print("Program continues executing normally without hanging or crashing.")

if __name__ == "__main__":
    main()
