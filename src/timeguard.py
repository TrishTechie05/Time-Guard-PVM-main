# =============================================================================
# FILE PURPOSE:
# This is the primary user-facing Python SDK library module.
# Developers import this file into their Python scripts to enforce execution deadlines.
# It provides:
#   1. 'with time_budget(ms):'  -> Context manager that bounds execution blocks.
#   2. '@time_guarded(ms=...)'   -> Function decorator that enforces call SLAs.
#   3. 'is_timeguard_supported()' -> Checks if current runtime supports TimeGuard.
#   4. 'set_budget_ms(ms)' & 'get_budget_ms()' -> Direct budget control functions.
# =============================================================================
"""
TimeGuard-PVM Python SDK
========================
This module provides high-level, Pythonic developer tools (such as context
managers and function decorators) that interface directly with the low-level
C-level execution guard built into the TimeGuard-PVM runtime.

How it works behind the scenes:
1. The custom CPython interpreter exposes two low-level C functions on 'sys':
   - sys.set_time_budget_ms(int): Sets the wall-clock deadline in milliseconds.
   - sys.get_time_budget_ms(): Returns the current active budget in milliseconds.
2. Inside the CPython bytecode evaluation loop (PVM), every backward jump and
   periodic check samples a POSIX monotonic clock.
3. If the elapsed wall-clock time exceeds the budget, the PVM immediately raises
   a RuntimeError("TimeGuard-PVM: execution time budget exceeded").
=============================================================================
"""

import sys
import contextlib
from typing import Optional, Callable, Any


def is_timeguard_supported() -> bool:
    """
    Check if the currently running Python interpreter has TimeGuard-PVM enabled.
    
    Returns:
        bool: True if this interpreter supports TimeGuard-PVM, False otherwise.
    """
    # Verify that both required C hooks exist in the sys module
    has_set_hook = hasattr(sys, "set_time_budget_ms")
    has_get_hook = hasattr(sys, "get_time_budget_ms")
    return has_set_hook and has_get_hook


def get_budget_ms() -> int:
    """
    Get the current active execution time budget in milliseconds.
    
    Returns:
        int: The active budget in milliseconds (0 means unlimited execution).
    """
    # If running on a standard Python interpreter without TimeGuard, return 0
    if not is_timeguard_supported():
        return 0
    
    # Query the C-level global state in the PVM
    return sys.get_time_budget_ms()


def set_budget_ms(ms: int) -> None:
    """
    Configure the execution time budget directly in milliseconds.
    
    Args:
        ms (int): Time limit in milliseconds. Pass 0 to disable the deadline.
        
    Raises:
        RuntimeError: If called on an interpreter without TimeGuard-PVM support.
        ValueError: If ms is negative.
    """
    # Guard against running on an unmodified Python interpreter
    if not is_timeguard_supported():
        raise RuntimeError(
            "TimeGuard-PVM is not supported on this interpreter.\n"
            "Please run your script using 'timeguard-python' or install the TimeGuard-PVM runtime."
        )
    
    # Validate input: negative budgets are invalid
    if ms < 0:
        raise ValueError(f"Time budget must be non-negative (received: {ms})")
    
    # Send the budget to the C-level evaluation loop
    sys.set_time_budget_ms(ms)


@contextlib.contextmanager
def time_budget(ms: int):
    """
    Context manager that enforces a hard wall-clock execution deadline on a block of code.
    
    When entering the block, the time budget is set to 'ms' milliseconds and the
    PVM's monotonic timer starts. When exiting the block (normally or via an
    exception), the previous budget is automatically restored.
    
    Args:
        ms (int): Maximum execution time in milliseconds allowed inside the block.
        
    Yields:
        None
        
    Raises:
        RuntimeError: Raised by the PVM if execution time exceeds 'ms'.
        
    Example:
        >>> with time_budget(100):
        ...     # This infinite loop will be cleanly aborted after ~100ms
        ...     while True:
        ...         pass
    """
    # Ensure the runtime supports TimeGuard
    if not is_timeguard_supported():
        raise RuntimeError(
            "TimeGuard-PVM is not supported on this interpreter.\n"
            "Please run your script using 'timeguard-python'."
        )
    
    # Save the existing budget so nested or sequential blocks preserve their configuration
    previous_budget = sys.get_time_budget_ms()
    
    # Arm the PVM watchdog with the new deadline
    sys.set_time_budget_ms(ms)
    try:
        # Execute the protected body of the 'with' statement
        yield
    finally:
        # Always restore the prior budget upon exit (guarantees cleanup even on error)
        sys.set_time_budget_ms(previous_budget)


def time_guarded(ms: int):
    """
    Function decorator that enforces an execution time limit on function calls.
    
    If the decorated function takes longer than 'ms' milliseconds to complete,
    the PVM halts execution and raises a RuntimeError.
    
    Args:
        ms (int): Maximum execution time allowed for each function call in milliseconds.
        
    Returns:
        Callable: The wrapped function protected by TimeGuard.
        
    Example:
        >>> @time_guarded(ms=250)
        ... def search_solution():
        ...     while True:
        ...         pass  # Aborts after ~250ms
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs) -> Any:
            # Wrap the actual function invocation inside our time_budget context manager
            with time_budget(ms):
                return func(*args, **kwargs)
        
        # Preserve original function metadata for introspection and documentation
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__
        return wrapper
        
    return decorator
