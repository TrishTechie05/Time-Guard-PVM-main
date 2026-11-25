#!/usr/bin/env timeguard-python
# =============================================================================
# FILE PURPOSE:
# This is the main runnable entry point for the TimeGuard project.
# It contains:
#   1. A complete commented architectural guide of every file in the codebase.
#   2. A runnable quick-start demo proving that TimeGuard cleanly halts infinite
#      loops inside the Python Virtual Machine (PVM) in ~100ms.
# Run it with:
#   timeguard-python src/main.py
# =============================================================================
#
# =============================================================================
# TIMEGUARD-PVM: COMPLETE CODEBASE MAP & ARCHITECTURAL GUIDE
# =============================================================================
#
# Welcome! This file serves as your central index and explanation of where every
# main file lives in this repository, what each file does, and how the pieces
# connect together to enforce execution deadlines inside Python.
#
# -----------------------------------------------------------------------------
# 1. THE MAIN PYTHON LIBRARY FILE (SDK)
# -----------------------------------------------------------------------------
# Location: src/timeguard.py (and src/__init__.py)
#
# What it is:
#   This is the high-level Python module that developers import into their
#   programs. It provides easy-to-use Pythonic tools:
#     - with time_budget(ms):  Context manager that bounds any block of code.
#     - @time_guarded(ms=...): Decorator that bounds any function execution.
#     - is_timeguard_supported(): Checks if the current interpreter has TimeGuard.
#     - set_budget_ms(ms) / get_budget_ms(): Direct helper functions.
#
# How it works:
#   It saves the existing budget, calls sys.set_time_budget_ms(ms) to arm the
#   virtual machine's watchdog, and restores the previous budget in a 'finally:'
#   block upon exiting.
#
# -----------------------------------------------------------------------------
# 2. THE MAIN BUILD & PATCH SCRIPT
# -----------------------------------------------------------------------------
# Location: scripts/patch_cpython.py (also available at ./patch_cpython.py)
#
# What it is:
#   The master automation script that injects the C-level TimeGuard logic into
#   a fresh copy of CPython's source code.
#
# What it modifies:
#   1. Include/internal/pycore_ceval.h:
#      Declares internal C global variables (_Py_timeguard_budget_ms,
#      _Py_timeguard_ticks) and functions so they can be accessed across files.
#   2. Python/ceval.c:
#      Implements the monotonic clock check using clock_gettime(CLOCK_MONOTONIC).
#      When elapsed >= budget, it disarms the deadline and raises a RuntimeError.
#   3. Python/ceval_macros.h:
#      Inlines the fast check into 'check_periodics' using '(ticks & 0xFF) == 0'.
#      This samples every 256 ticks, reducing clock syscall overhead to <0.5%.
#   4. Python/sysmodule.c:
#      Exposes sys.set_time_budget_ms(ms) and sys.get_time_budget_ms() in Python,
#      and parses the 'TIMEGUARD_MS' environment variable at startup.
#   5. Python/getversion.c:
#      Brands the version string with '[TimeGuard-PVM]'.
#   6. Lib/platform.py:
#      Updates Python's version regex so 'pip' and 'ensurepip' remain compatible.
#
# -----------------------------------------------------------------------------
# 3. THE MAIN TEST & VERIFICATION SUITE
# -----------------------------------------------------------------------------
# Location: tests/test_timeguard.py
#
# What it is:
#   The automated test suite that validates the runtime under 5 conditions:
#     - Test 1: Fast loops complete safely under a generous budget (2000ms).
#     - Test 2: An infinite 'while True:' loop halts cleanly in ~100ms.
#     - Test 3: Disabling the budget (0ms) allows normal unconstrained execution.
#     - Test 4: 'with time_budget(ms):' context manager bounds code and restores state.
#     - Test 5: '@time_guarded(ms=...)' decorator enforces function call SLAs.
#
# How to run:
#   timeguard-python tests/test_timeguard.py
#
# -----------------------------------------------------------------------------
# 4. IN THE CPYTHON RUNTIME SOURCE (INSIDE WSL / LINUX)
# -----------------------------------------------------------------------------
# Location: ~/pvm-timeguard/cpython-src/Python/ceval.c
#
# What it is:
#   The core C source file inside the CPython repository that implements the
#   Bytecode Evaluation Loop (_PyEval_EvalFrameDefault).
#   This is the actual "engine" where the Python Virtual Machine (PVM)
#   evaluates opcodes and interrupts runaway loops.
#
# -----------------------------------------------------------------------------
# 5. THE INSTALLED EXECUTABLE BINARY
# -----------------------------------------------------------------------------
# Location: /usr/local/bin/timeguard-python (points to /opt/timeguard-pvm/bin/python3.16)
#
# What it is:
#   The compiled custom Python interpreter on your machine. You can run any
#   Python script with it:
#     timeguard-python my_script.py
#     TIMEGUARD_MS=200 timeguard-python my_script.py
#
# -----------------------------------------------------------------------------
# 6. RUNNABLE EXAMPLES FOLDER
# -----------------------------------------------------------------------------
# Location: examples/
#   - examples/01_basic_usage.py: Direct sys.set_time_budget_ms usage.
#   - examples/02_context_manager.py: 'with time_budget(ms):' usage.
#   - examples/03_function_decorator.py: '@time_guarded(ms=...)' usage.
#   - examples/04_untrusted_code.py: Safely executing untrusted user code strings.
#
# =============================================================================

import sys
import time

# Import our helper SDK from the same directory
from timeguard import (
    is_timeguard_supported,
    get_budget_ms,
    set_budget_ms,
    time_budget,
    time_guarded,
)


def run_quick_demo():
    """
    A simple, runnable demonstration proving that this file and TimeGuard work.
    """
    print("=" * 70)
    print("TIMEGUARD-PVM QUICK START DEMO")
    print("=" * 70)
    print(f"Interpreter:         {sys.version}")
    print(f"TimeGuard Active:    {is_timeguard_supported()}")
    print(f"Initial Time Budget: {get_budget_ms()} ms (0 = unlimited)")
    print("-" * 70)

    # Demonstrate bounding a loop to 100 milliseconds
    deadline_ms = 100
    print(f"\n[DEMO] Starting an intentional infinite loop bounded to {deadline_ms} ms...")
    
    start_time = time.monotonic()
    try:
        with time_budget(deadline_ms):
            # This infinite loop would freeze a standard Python process forever.
            # In TimeGuard-PVM, the bytecode evaluation loop aborts it automatically.
            iterations = 0
            while True:
                iterations += 1

    except RuntimeError as error:
        elapsed_ms = (time.monotonic() - start_time) * 1000.0
        print(f"\n[SUCCESS] TimeGuard cleanly aborted the runaway loop!")
        print(f"  -> Elapsed Wall-Clock: {elapsed_ms:.2f} ms (Target was ~{deadline_ms} ms)")
        print(f"  -> Total Iterations:   {iterations:,}")
        print(f"  -> Exception Caught:   '{error}'")

    print("\n[INFO] Normal program execution continues smoothly below.")
    print("=" * 70)


if __name__ == "__main__":
    run_quick_demo()
