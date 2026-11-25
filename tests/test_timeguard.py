#!/usr/bin/env timeguard-python
# =============================================================================
# FILE PURPOSE:
# This is the automated verification and regression test suite for TimeGuard-PVM.
# It rigorously tests 5 core execution conditions:
#   1. Generous deadlines (2000ms): Fast loops complete without interference.
#   2. Short deadlines (100ms): Infinite loops halt near 100ms with RuntimeError.
#   3. Watchdog reset (0ms): Execution unconstrained after disarming budget.
#   4. Context manager: 'with time_budget(ms):' isolates and restores state.
#   5. Function decorator: '@time_guarded(ms=...)' bounds individual function calls.
# Run it with:
#   timeguard-python tests/test_timeguard.py
# =============================================================================
"""
=============================================================================
TimeGuard-PVM Automated Test Suite
=============================================================================
Validates:
1. Runtime identification & banner verification.
2. Low-level 'sys.set_time_budget_ms(ms)' and 'sys.get_time_budget_ms()'.
3. Normal fast loops completing well within generous deadlines.
4. Clean, uncorrupted abort of runaway loops ('while True:') near deadline target.
5. Watchdog disarming & clean resumption of normal execution with budget 0.
6. High-level 'with time_budget(ms):' context manager behavior & stack restoration.
7. High-level '@time_guarded(ms=...)' function decorator SLA enforcement.
=============================================================================
"""

import os
import sys
import time

# Ensure 'src' is on sys.path so 'timeguard' can be imported regardless of current working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from timeguard import (
    is_timeguard_supported,
    get_budget_ms,
    set_budget_ms,
    time_budget,
    time_guarded,
)


def run_all_tests():
    print("=" * 70)
    print("RUNNING TIMEGUARD-PVM AUTOMATED VERIFICATION SUITE")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Initial Sanity Checks: Runtime identity
    # -----------------------------------------------------------------------
    print(f"[INFO] Python Version String: {sys.version}")
    print(f"[INFO] TimeGuard Supported:   {is_timeguard_supported()}")
    
    assert is_timeguard_supported(), (
        "Assertion Error: TimeGuard-PVM is not detected on this interpreter!\n"
        "Please run this test with: timeguard-python tests/test_timeguard.py"
    )

    # Default budget should always be 0 (unlimited)
    initial_budget = get_budget_ms()
    print(f"[INFO] Initial Time Budget:   {initial_budget} ms")
    assert initial_budget == 0, f"Expected initial budget 0, got {initial_budget}"

    # -----------------------------------------------------------------------
    # TEST 1: Fast loop completes cleanly within generous budget
    # -----------------------------------------------------------------------
    # When a generous budget is configured (e.g. 2000ms), fast operations
    # that finish well under 2000ms should execute to completion without error.
    # -----------------------------------------------------------------------
    print("\n--- TEST 1: Normal fast loop with generous budget (2000ms) ---")
    set_budget_ms(2000)
    assert get_budget_ms() == 2000, "Budget failed to set to 2000ms"
    
    t0 = time.monotonic()
    # Perform a 100,000 iteration accumulation
    total = sum(i for i in range(100_000))
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    
    print(f"  -> Sum: {total}")
    print(f"  -> Execution elapsed: {elapsed_ms:.2f} ms")
    assert elapsed_ms < 1500, f"Fast loop took too long: {elapsed_ms}ms"
    print("  [PASS] Test 1 completed safely within budget.")

    # -----------------------------------------------------------------------
    # TEST 2: Tight infinite loop halts near 100ms deadline
    # -----------------------------------------------------------------------
    # An infinite 'while True: pass' loop must be interrupted by the PVM
    # within approximately 100ms with a clean RuntimeError.
    # -----------------------------------------------------------------------
    print("\n--- TEST 2: Runaway 'while True:' loop with 100ms deadline ---")
    set_budget_ms(100)
    assert get_budget_ms() == 100, "Budget failed to set to 100ms"

    caught_runtime_error = False
    caught_message = ""
    t0 = time.monotonic()
    
    try:
        # Runaway loop that would hang forever without TimeGuard
        while True:
            pass
    except RuntimeError as exc:
        t1 = time.monotonic()
        elapsed_ms = (t1 - t0) * 1000.0
        caught_runtime_error = True
        caught_message = str(exc)
        print(f"  -> Successfully caught timeout after {elapsed_ms:.2f} ms")
        print(f"  -> Exception message: '{caught_message}'")
        
        # Verify the specific error message generated by the PVM
        assert "TimeGuard-PVM: execution time budget exceeded" in caught_message, (
            f"Unexpected exception message: {caught_message}"
        )
        
        # Verify precision: should be close to 100ms (within 80ms - 250ms tolerance)
        assert 80 <= elapsed_ms <= 300, (
            f"Timing error: Aborted in {elapsed_ms}ms, expected ~100ms"
        )

    assert caught_runtime_error, "Failed: RuntimeError was not raised by PVM!"
    print("  [PASS] Test 2 cleanly aborted infinite loop near 100ms deadline.")

    # -----------------------------------------------------------------------
    # TEST 3: Disabling budget and resuming normal execution
    # -----------------------------------------------------------------------
    # Calling sys.set_time_budget_ms(0) must disarm the watchdog completely,
    # allowing code that takes longer than 100ms to run without interruption.
    # -----------------------------------------------------------------------
    print("\n--- TEST 3: Disabling budget (set_budget_ms(0)) ---")
    set_budget_ms(0)
    assert get_budget_ms() == 0, "Budget was not 0 after disabling"

    t0 = time.monotonic()
    iterations = 0
    # Run a loop for 200ms (longer than the previous 100ms deadline)
    while time.monotonic() - t0 < 0.20:
        iterations += 1
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    
    print(f"  -> Normal loop ran for {elapsed_ms:.2f} ms ({iterations:,} iterations)")
    assert elapsed_ms >= 190.0, f"Loop finished prematurely: {elapsed_ms}ms"
    print("  [PASS] Test 3 confirmed normal execution resumes unconstrained.")

    # -----------------------------------------------------------------------
    # TEST 4: Pythonic Context Manager ('with time_budget(ms):')
    # -----------------------------------------------------------------------
    # Validates that the context manager:
    # 1. Enforces the deadline inside the 'with' block.
    # 2. Automatically restores the previous budget (0) on exit.
    # -----------------------------------------------------------------------
    print("\n--- TEST 4: Context manager ('with time_budget(120):') ---")
    assert get_budget_ms() == 0, "Pre-condition failed: budget should be 0"

    caught_ctx_error = False
    t0 = time.monotonic()
    try:
        with time_budget(120):
            while True:
                pass
    except RuntimeError as exc:
        t1 = time.monotonic()
        elapsed_ms = (t1 - t0) * 1000.0
        caught_ctx_error = True
        print(f"  -> Context manager caught timeout after {elapsed_ms:.2f} ms")
        assert "TimeGuard-PVM" in str(exc)
        assert 90 <= elapsed_ms <= 350

    assert caught_ctx_error, "Context manager failed to interrupt infinite loop"
    # Ensure budget was restored to 0 upon exiting the with-block
    assert get_budget_ms() == 0, f"Budget not restored: {get_budget_ms()}"
    print("  [PASS] Test 4 context manager bounded loop and restored budget state.")

    # -----------------------------------------------------------------------
    # TEST 5: Function Decorator ('@time_guarded(ms=80)')
    # -----------------------------------------------------------------------
    # Validates that the decorator enforces a deadline on function calls.
    # -----------------------------------------------------------------------
    print("\n--- TEST 5: Decorator ('@time_guarded(ms=80)') ---")
    
    @time_guarded(ms=80)
    def runaway_solver():
        # Simulates an algorithm that enters an accidental loop
        counter = 0
        while True:
            counter += 1
        return counter

    caught_decorator_error = False
    t0 = time.monotonic()
    try:
        runaway_solver()
    except RuntimeError as exc:
        t1 = time.monotonic()
        elapsed_ms = (t1 - t0) * 1000.0
        caught_decorator_error = True
        print(f"  -> Decorated function caught timeout after {elapsed_ms:.2f} ms")
        assert "TimeGuard-PVM" in str(exc)
        assert 60 <= elapsed_ms <= 250

    assert caught_decorator_error, "Decorator failed to interrupt runaway function"
    assert get_budget_ms() == 0, "Budget not restored after decorator exit"
    print("  [PASS] Test 5 decorator successfully bounded function execution.")

    print("\n" + "=" * 70)
    print("ALL 5 TIMEGUARD-PVM TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
