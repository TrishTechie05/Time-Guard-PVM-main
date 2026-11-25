#!/usr/bin/env python3
# =============================================================================
# FILE PURPOSE:
# This is the master CPython source code patcher.
# It automatically modifies 6 CPython files to embed the TimeGuard watchdog
# directly inside the Python Virtual Machine (PVM) bytecode evaluation loop.
# It contains the ORIGINAL CPython code in comments side-by-side with the NEW code
# so you can easily compare and review the modifications.
# Run it with:
#   python3 scripts/patch_cpython.py [path_to_cpython_src]
# =============================================================================
"""
=============================================================================
TimeGuard-PVM CPython Source Patcher (With Side-by-Side Original Code)
=============================================================================
This script automatically injects the TimeGuard execution deadline guard into
a local clone of the CPython source tree.

For every modification, the ORIGINAL CPython code is preserved in comments
directly alongside the NEW / MODIFIED code, allowing you to easily compare
both implementations.

The 6 modification sites are:
1. Include/internal/pycore_ceval.h (C Declarations)
2. Python/ceval.c                  (Monotonic Clock & State Implementation)
3. Python/ceval_macros.h           (Bytecode Periodic Check & 256-Tick Sampling)
4. Python/sysmodule.c              (Python sys.set/get_time_budget_ms API)
5. Python/getversion.c             (Version Banner Branding)
6. Lib/platform.py                 (Version Parser Compatibility)
=============================================================================
"""

import os
import sys

# Default path to CPython source tree
DEFAULT_REPO_DIR = os.path.expanduser('~/pvm-timeguard/cpython-src')
repo_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPO_DIR

if not os.path.isdir(repo_dir):
    print(f"Error: CPython source directory not found at: {repo_dir}")
    print("Usage: python3 patch_cpython.py [path_to_cpython_src]")
    sys.exit(1)

print("=" * 70)
print(f"Applying TimeGuard-PVM Patches to: {repo_dir}")
print("=" * 70)


# ===========================================================================
# SITE 1: Include/internal/pycore_ceval.h
# ===========================================================================
# COMPARISON:
#
# --- ORIGINAL CPYTHON CODE ---
# struct _ceval_runtime_state;
#
# // Export for '_lsprof' shared extension
# PyAPI_FUNC(int) _PyEval_SetProfile(PyThreadState *tstate, ...);
#
# --- MODIFIED / TIMEGUARD-PVM CODE ---
# struct _ceval_runtime_state;
#
# /* [TimeGuard-PVM]: Export declarations for time budget state and functions */
# PyAPI_DATA(long long) _Py_timeguard_budget_ms;
# PyAPI_DATA(uint64_t) _Py_timeguard_ticks;
# PyAPI_FUNC(int) _Py_TimeGuard_Check_Slow(PyThreadState *tstate);
# PyAPI_FUNC(void) _Py_TimeGuard_SetBudgetMS(long long ms);
# PyAPI_FUNC(long long) _Py_TimeGuard_GetBudgetMS(void);
# PyAPI_FUNC(void) _Py_TimeGuard_Init(void);
# ===========================================================================

ceval_h_path = os.path.join(repo_dir, 'Include/internal/pycore_ceval.h')
with open(ceval_h_path, 'r', encoding='utf-8') as f:
    content = f.read()

guard_decl = '''
/* =========================================================================
 * [TimeGuard-PVM]: Execution budget guard declarations
 *
 * ORIGINAL CPYTHON:
 *   (Nothing existed here; CPython had no native time-budgeting globals).
 *
 * MODIFIED TIMEGUARD-PVM:
 *   Declare global state and functions so ceval.c, ceval_macros.h, and
 *   sysmodule.c can share the watchdog timer.
 * ========================================================================= */
PyAPI_DATA(long long) _Py_timeguard_budget_ms;     // Active budget in milliseconds (0 = disabled)
PyAPI_DATA(uint64_t) _Py_timeguard_ticks;          // Monotonic bytecode tick counter
PyAPI_FUNC(int) _Py_TimeGuard_Check_Slow(PyThreadState *tstate); // Clock query & exception trigger
PyAPI_FUNC(void) _Py_TimeGuard_SetBudgetMS(long long ms);        // Configure / arm deadline
PyAPI_FUNC(long long) _Py_TimeGuard_GetBudgetMS(void);           // Query active deadline
PyAPI_FUNC(void) _Py_TimeGuard_Init(void);                       // Parse TIMEGUARD_MS env variable
'''

if '_Py_TimeGuard_SetBudgetMS' not in content:
    target = 'struct _ceval_runtime_state;'
    assert target in content, 'Target "struct _ceval_runtime_state;" not found in pycore_ceval.h'
    content = content.replace(target, target + '\n' + guard_decl, 1)
    with open(ceval_h_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('  [+] SITE 1: Patched Include/internal/pycore_ceval.h')
else:
    print('  [=] SITE 1: Include/internal/pycore_ceval.h is already up-to-date')


# ===========================================================================
# SITE 2: Python/ceval.c
# ===========================================================================
# COMPARISON:
#
# --- ORIGINAL CPYTHON CODE ---
# /* Execute compiled code */
# #include "ceval.h"
# #include "pycore_long.h"
#
# --- MODIFIED / TIMEGUARD-PVM CODE ---
# /* Execute compiled code */
# #include "ceval.h"
#
# /* [TimeGuard-PVM]: Monotonic clock tracking and budget enforcement */
# #include <time.h>
# #include <sys/time.h>
# ... implementation of _Py_TimeGuard_SetBudgetMS, _Py_TimeGuard_Check_Slow ...
# ===========================================================================

ceval_c_path = os.path.join(repo_dir, 'Python/ceval.c')
with open(ceval_c_path, 'r', encoding='utf-8') as f:
    content = f.read()

guard_impl = '''
/* =========================================================================
 * [TimeGuard-PVM]: Monotonic clock tracking and budget enforcement
 *
 * ORIGINAL CPYTHON:
 *   Directly included "pycore_long.h" after "ceval.h" with no deadline logic.
 *
 * MODIFIED TIMEGUARD-PVM:
 *   Added high-precision POSIX monotonic clock sampling and auto-disarming
 *   watchdog logic.
 * ========================================================================= */
#include <time.h>
#include <sys/time.h>

long long _Py_timeguard_budget_ms = 0;              // Active budget in ms (0 = unlimited)
uint64_t _Py_timeguard_ticks = 0;                   // Counter incremented per periodic check
static struct timespec _Py_timeguard_start_time = {0, 0}; // Monotonic start timestamp

// Arm or disarm the execution deadline
void
_Py_TimeGuard_SetBudgetMS(long long ms)
{
    if (ms <= 0) {
        // Disarm deadline: 0 means unlimited execution
        _Py_timeguard_budget_ms = 0;
    } else {
        // Arm deadline: Record budget and capture current monotonic start time
        _Py_timeguard_budget_ms = ms;
        _Py_timeguard_ticks = 0;
#if defined(CLOCK_MONOTONIC)
        clock_gettime(CLOCK_MONOTONIC, &_Py_timeguard_start_time);
#else
        // Fallback for non-POSIX platforms
        struct timeval tv;
        gettimeofday(&tv, NULL);
        _Py_timeguard_start_time.tv_sec = tv.tv_sec;
        _Py_timeguard_start_time.tv_nsec = tv.tv_usec * 1000;
#endif
    }
}

// Return the current budget (or 0 if inactive)
long long
_Py_TimeGuard_GetBudgetMS(void)
{
    return _Py_timeguard_budget_ms;
}

// Check for the TIMEGUARD_MS environment variable during startup
void
_Py_TimeGuard_Init(void)
{
    const char *env = Py_GETENV("TIMEGUARD_MS");
    if (env != NULL && *env != '\\0') {
        long long ms = atoll(env);
        if (ms > 0) {
            _Py_TimeGuard_SetBudgetMS(ms);
        }
    }
}

// Called every 256 ticks to check elapsed wall-clock time
int
_Py_TimeGuard_Check_Slow(PyThreadState *tstate)
{
    if (_Py_timeguard_budget_ms <= 0) {
        return 0; // Guard is inactive
    }

    // Query current monotonic time
    struct timespec now;
#if defined(CLOCK_MONOTONIC)
    clock_gettime(CLOCK_MONOTONIC, &now);
#else
    struct timeval tv;
    gettimeofday(&tv, NULL);
    now.tv_sec = tv.tv_sec;
    now.tv_nsec = tv.tv_usec * 1000;
#endif

    // Calculate elapsed milliseconds: (sec * 1000) + (nsec / 1,000,000)
    long long elapsed_ms = (long long)(now.tv_sec - _Py_timeguard_start_time.tv_sec) * 1000LL +
                           (long long)(now.tv_nsec - _Py_timeguard_start_time.tv_nsec) / 1000000LL;

    // Check if the wall-clock deadline has been breached
    if (elapsed_ms >= _Py_timeguard_budget_ms) {
        // [IMPORTANT]: Disarm the deadline immediately upon firing!
        // This allows user exception handlers (try...except RuntimeError)
        // and traceback generators to execute cleanly without immediately re-tripping.
        _Py_timeguard_budget_ms = 0;

        // Set the RuntimeError in the Python interpreter state
        PyErr_SetString(PyExc_RuntimeError, "TimeGuard-PVM: execution time budget exceeded");
        return -1; // Signals error to the bytecode loop
    }
    return 0;
}
'''

if '_Py_TimeGuard_SetBudgetMS' not in content:
    target = '#include "ceval.h"'
    assert target in content, 'Target \'#include "ceval.h"\' not found in ceval.c'
    content = content.replace(target, target + '\n' + guard_impl, 1)
    with open(ceval_c_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('  [+] SITE 2: Patched Python/ceval.c')
else:
    print('  [=] SITE 2: Python/ceval.c is already up-to-date')


# ===========================================================================
# SITE 3: Python/ceval_macros.h
# ===========================================================================
# COMPARISON:
#
# --- ORIGINAL CPYTHON CODE ---
# static inline int
# check_periodics(PyThreadState *tstate) {
#     _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
#     QSBR_QUIESCENT_STATE(tstate);
#     if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
#         return _Py_HandlePending(tstate);
#     }
#     return 0;
# }
#
# --- MODIFIED / TIMEGUARD-PVM CODE ---
# static inline int
# _Py_TimeGuard_Check(PyThreadState *tstate) {
#     if (_Py_timeguard_budget_ms <= 0) return 0;
#     if ((++_Py_timeguard_ticks & 0xFF) != 0) return 0; // Check every 256 ticks
#     return _Py_TimeGuard_Check_Slow(tstate);
# }
#
# static inline int
# check_periodics(PyThreadState *tstate) {
#     if (_Py_TimeGuard_Check(tstate) != 0) return -1; // TimeGuard deadline check
#     _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
#     ...
# }
# ===========================================================================

ceval_macros_h_path = os.path.join(repo_dir, 'Python/ceval_macros.h')
with open(ceval_macros_h_path, 'r', encoding='utf-8') as f:
    content = f.read()

target_periodics = '''static inline int
check_periodics(PyThreadState *tstate) {
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        return _Py_HandlePending(tstate);
    }
    return 0;
}'''

replacement_periodics = '''/* =========================================================================
 * [TimeGuard-PVM]: Inlined fast tick check
 *
 * ORIGINAL CPYTHON:
 *   Had no tick sampling; check_periodics only checked eval_breaker bitmask.
 *
 * MODIFIED TIMEGUARD-PVM:
 *   1. Check if budget > 0 (1 fast CPU comparison).
 *   2. Increment ticks and mask with 0xFF: only 1 in 256 ticks calls clock_gettime!
 *   3. If deadline exceeded, returns -1, causing opcode to jump to error unwinding.
 * ========================================================================= */
static inline int
_Py_TimeGuard_Check(PyThreadState *tstate) {
    if (_Py_timeguard_budget_ms <= 0) {
        return 0; // Zero overhead when budget is disabled
    }
    // Sub-nanosecond bitmask: skip clock syscalls for 255 out of 256 iterations
    if ((++_Py_timeguard_ticks & 0xFF) != 0) {
        return 0;
    }
    return _Py_TimeGuard_Check_Slow(tstate);
}

static inline int
check_periodics(PyThreadState *tstate) {
    /* [TimeGuard-PVM]: First check the execution deadline */
    if (_Py_TimeGuard_Check(tstate) != 0) {
        return -1;
    }
    /* ORIGINAL CPYTHON LOGIC: */
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        return _Py_HandlePending(tstate);
    }
    return 0;
}'''

target_periodics_end = '''static inline int
check_periodics_at_end(PyThreadState *tstate, _PyInterpreterFrame *frame) {
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        // Do not handle pending interrupts if the previous instruction was LOAD_SPECIAL
        // This may also not handle interrupts if a cache looks like LOAD_SPECIAL,
        // but this is benign as we won't skip periodic checks indefinitely.
        if (frame->instr_ptr[-1].op.code == LOAD_SPECIAL) {
            return 0;
        }
        return _Py_HandlePending(tstate);
    }
    return 0;
}'''

replacement_periodics_end = '''static inline int
check_periodics_at_end(PyThreadState *tstate, _PyInterpreterFrame *frame) {
    /* [TimeGuard-PVM]: First check the execution deadline */
    if (_Py_TimeGuard_Check(tstate) != 0) {
        return -1;
    }
    /* ORIGINAL CPYTHON LOGIC: */
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        // Do not handle pending interrupts if the previous instruction was LOAD_SPECIAL
        // This may also not handle interrupts if a cache looks like LOAD_SPECIAL,
        // but this is benign as we won't skip periodic checks indefinitely.
        if (frame->instr_ptr[-1].op.code == LOAD_SPECIAL) {
            return 0;
        }
        return _Py_HandlePending(tstate);
    }
    return 0;
}'''

if '_Py_TimeGuard_Check' not in content:
    assert target_periodics in content, 'target_periodics not found in ceval_macros.h'
    assert target_periodics_end in content, 'target_periodics_end not found in ceval_macros.h'
    content = content.replace(target_periodics, replacement_periodics, 1)
    content = content.replace(target_periodics_end, replacement_periodics_end, 1)
    with open(ceval_macros_h_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('  [+] SITE 3: Patched Python/ceval_macros.h')
else:
    print('  [=] SITE 3: Python/ceval_macros.h is already up-to-date')


# ===========================================================================
# SITE 4: Python/sysmodule.c
# ===========================================================================
# COMPARISON:
#
# --- ORIGINAL CPYTHON CODE ---
# static PyMethodDef sys_methods[] = {
#     SYS_ADDAUDITHOOK_METHODDEF
#     ...
#
# --- MODIFIED / TIMEGUARD-PVM CODE ---
# static PyObject *
# sys_set_time_budget_ms(PyObject *self, PyObject *args) { ... }
#
# static PyObject *
# sys_get_time_budget_ms(PyObject *self, PyObject *Py_UNUSED(ignored)) { ... }
#
# static PyMethodDef sys_methods[] = {
#     {"set_time_budget_ms", sys_set_time_budget_ms, METH_VARARGS, ...},
#     {"get_time_budget_ms", sys_get_time_budget_ms, METH_NOARGS, ...},
#     SYS_ADDAUDITHOOK_METHODDEF
#     ...
# And in _PySys_InitCore:
#     _Py_TimeGuard_Init();
# ===========================================================================

sysmodule_c_path = os.path.join(repo_dir, 'Python/sysmodule.c')
with open(sysmodule_c_path, 'r', encoding='utf-8') as f:
    content = f.read()

sys_methods_code = '''
/* =========================================================================
 * [TimeGuard-PVM]: sys.set_time_budget_ms and sys.get_time_budget_ms
 *
 * ORIGINAL CPYTHON:
 *   Did not provide execution deadline control functions.
 *
 * MODIFIED TIMEGUARD-PVM:
 *   Expose set_time_budget_ms(ms) and get_time_budget_ms() to Python scripts.
 * ========================================================================= */
static PyObject *
sys_set_time_budget_ms(PyObject *self, PyObject *args)
{
    long long ms;
    if (!PyArg_ParseTuple(args, "L:set_time_budget_ms", &ms)) {
        return NULL;
    }
    if (ms < 0) {
        PyErr_SetString(PyExc_ValueError, "time budget must be non-negative");
        return NULL;
    }
    _Py_TimeGuard_SetBudgetMS(ms);
    Py_RETURN_NONE;
}

static PyObject *
sys_get_time_budget_ms(PyObject *self, PyObject *Py_UNUSED(ignored))
{
    return PyLong_FromLongLong(_Py_TimeGuard_GetBudgetMS());
}
'''

if 'sys_set_time_budget_ms' not in content:
    target = 'static PyMethodDef sys_methods[] = {'
    assert target in content, 'Target "sys_methods" not found in sysmodule.c'
    content = content.replace(target, sys_methods_code + '\n' + target + '\n    {"set_time_budget_ms", sys_set_time_budget_ms, METH_VARARGS, "set_time_budget_ms(ms) -> Set execution time budget in milliseconds (0 to disable)."},' + '\n    {"get_time_budget_ms", sys_get_time_budget_ms, METH_NOARGS, "get_time_budget_ms() -> Get current execution time budget in milliseconds."},', 1)

    init_target = '_PySys_InitCore(PyThreadState *tstate, PyObject *sysdict)\n{'
    assert init_target in content, 'Target "_PySys_InitCore" not found in sysmodule.c'
    content = content.replace(init_target, init_target + '\n    /* [TimeGuard-PVM]: Initialize budget from TIMEGUARD_MS environment variable */\n    _Py_TimeGuard_Init();', 1)

    with open(sysmodule_c_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('  [+] SITE 4: Patched Python/sysmodule.c')
else:
    print('  [=] SITE 4: Python/sysmodule.c is already up-to-date')


# ===========================================================================
# SITE 5: Python/getversion.c
# ===========================================================================
# COMPARISON:
#
# --- ORIGINAL CPYTHON CODE ---
# const char *buildinfo_format = "%.80s (%.80s) %.80s";
#
# --- MODIFIED / TIMEGUARD-PVM CODE ---
# const char *buildinfo_format = "%.80s [TimeGuard-PVM] (%.80s) %.80s";
# ===========================================================================

getversion_c_path = os.path.join(repo_dir, 'Python/getversion.c')
with open(getversion_c_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'TimeGuard-PVM' not in content:
    # Tag both free-threaded and standard builds with [TimeGuard-PVM]
    content = content.replace('"%.80s free-threading build (%.80s) %.80s";', '"%.80s free-threading build [TimeGuard-PVM] (%.80s) %.80s";', 1)
    content = content.replace('"%.80s (%.80s) %.80s";', '"%.80s [TimeGuard-PVM] (%.80s) %.80s";', 1)
    with open(getversion_c_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('  [+] SITE 5: Patched Python/getversion.c')
else:
    print('  [=] SITE 5: Python/getversion.c is already up-to-date')


# ===========================================================================
# SITE 6: Lib/platform.py
# ===========================================================================
# COMPARISON:
#
# --- ORIGINAL CPYTHON CODE ---
# cpython_sys_version_parser = re.compile(
#     r'([\w.+]+)\s*'  # "version<space>"
#     r'(?:free-threading build\s+)?' # "free-threading-build<space>"
#     r'\(#?([^,]+)'  # "(#buildno"
#
# --- MODIFIED / TIMEGUARD-PVM CODE ---
# cpython_sys_version_parser = re.compile(
#     r'([\w.+]+)\s*'  # "version<space>"
#     r'(?:free-threading build\s+)?' # "free-threading-build<space>"
#     r'(?:\[TimeGuard-PVM\]\s+)?'   # Allow [TimeGuard-PVM] tag
#     r'\(#?([^,]+)'  # "(#buildno"
# ===========================================================================

platform_py_path = os.path.join(repo_dir, 'Lib/platform.py')
with open(platform_py_path, 'r', encoding='utf-8') as f:
    pcontent = f.read()

if 'TimeGuard-PVM' not in pcontent:
    target = "r'(?:free-threading build\\s+)?' # \"free-threading-build<space>\""
    replacement = target + "\n            # [TimeGuard-PVM]: Allow [TimeGuard-PVM] tag in version parser\n            r'(?:\\[TimeGuard-PVM\\]\\s+)?'"
    assert target in pcontent, 'Target "free-threading build" not found in platform.py'
    pcontent = pcontent.replace(target, replacement, 1)
    with open(platform_py_path, 'w', encoding='utf-8') as f:
        f.write(pcontent)
    print('  [+] SITE 6: Patched Lib/platform.py')
else:
    print('  [=] SITE 6: Lib/platform.py is already up-to-date')

print("=" * 70)
print("All 6 TimeGuard-PVM source sites successfully patched!")
print("=" * 70)
