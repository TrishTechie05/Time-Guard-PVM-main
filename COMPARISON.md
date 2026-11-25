# TimeGuard-PVM Code Comparison & Architecture Breakdown 🔍

This document presents a side-by-side comparison between the **Original CPython source code** and the **TimeGuard-PVM modified code** across all 6 modification sites.

---

## Table of Contents
1. [Site 1: `Include/internal/pycore_ceval.h` (C Declarations)](#site-1-includeinternalpycore_cevalh-c-declarations)
2. [Site 2: `Python/ceval.c` (Monotonic Clock & State Implementation)](#site-2-pythoncevalc-monotonic-clock--state-implementation)
3. [Site 3: `Python/ceval_macros.h` (Bytecode Periodic Check & 256-Tick Sampling)](#site-3-pythonceval_macrosh-bytecode-periodic-check--256-tick-sampling)
4. [Site 4: `Python/sysmodule.c` (Python `sys.set/get_time_budget_ms` API)](#site-4-pythonsysmodulec-python-syssetget_time_budget_ms-api)
5. [Site 5: `Python/getversion.c` (Version Banner Branding)](#site-5-pythongetversionc-version-banner-branding)
6. [Site 6: `Lib/platform.py` (Version Parser Compatibility)](#site-6-libplatformpy-version-parser-compatibility)

---

## Site 1: `Include/internal/pycore_ceval.h` (C Declarations)

### Original CPython Code:
```c
/* Forward declarations */
struct _ceval_runtime_state;

// Export for '_lsprof' shared extension
PyAPI_FUNC(int) _PyEval_SetProfile(PyThreadState *tstate, Py_tracefunc func, PyObject *arg);
extern int _PyEval_SetProfileAllThreads(PyInterpreterState *interp, Py_tracefunc func, PyObject *arg);
```

### TimeGuard-PVM Modified Code:
```c
/* Forward declarations */
struct _ceval_runtime_state;

/* =========================================================================
 * [TimeGuard-PVM]: Execution budget guard declarations
 * ========================================================================= */
PyAPI_DATA(long long) _Py_timeguard_budget_ms;     // Active budget in milliseconds (0 = disabled)
PyAPI_DATA(uint64_t) _Py_timeguard_ticks;          // Monotonic bytecode tick counter
PyAPI_FUNC(int) _Py_TimeGuard_Check_Slow(PyThreadState *tstate); // Clock query & exception trigger
PyAPI_FUNC(void) _Py_TimeGuard_SetBudgetMS(long long ms);        // Configure / arm deadline
PyAPI_FUNC(long long) _Py_TimeGuard_GetBudgetMS(void);           // Query active deadline
PyAPI_FUNC(void) _Py_TimeGuard_Init(void);                       // Parse TIMEGUARD_MS env variable

// Export for '_lsprof' shared extension
PyAPI_FUNC(int) _PyEval_SetProfile(PyThreadState *tstate, Py_tracefunc func, PyObject *arg);
extern int _PyEval_SetProfileAllThreads(PyInterpreterState *interp, Py_tracefunc func, PyObject *arg);
```

### 💡 Why this was changed:
- CPython's evaluation state is partitioned across several translation units (`ceval.c`, `sysmodule.c`, and `ceval_macros.h`).
- Declaring `_Py_timeguard_budget_ms` with `PyAPI_DATA` and functions with `PyAPI_FUNC` ensures they can be shared globally throughout the runtime without linkage errors.

---

## Site 2: `Python/ceval.c` (Monotonic Clock & State Implementation)

### Original CPython Code:
```c
/* Execute compiled code */

#include "ceval.h"
#include "pycore_long.h"
```

### TimeGuard-PVM Modified Code:
```c
/* Execute compiled code */

#include "ceval.h"

/* =========================================================================
 * [TimeGuard-PVM]: Monotonic clock tracking and budget enforcement
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
    if (env != NULL && *env != '\0') {
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

#include "pycore_long.h"
```

### 💡 Why this was changed:
1. **`CLOCK_MONOTONIC`**: Unlike wall-clock real time (`gettimeofday`), a monotonic clock never jumps backward due to NTP synchronization or daylight saving adjustments.
2. **Auto-Disarming (`_Py_timeguard_budget_ms = 0`)**: If the deadline remained active after firing, the very next instruction executed inside a Python `except RuntimeError:` block would immediately re-trigger a second timeout exception. Disarming allows exception handlers to catch and process the error cleanly.

---

## Site 3: `Python/ceval_macros.h` (Bytecode Periodic Check & 256-Tick Sampling)

### Original CPython Code:
```c
static inline int
check_periodics(PyThreadState *tstate) {
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        return _Py_HandlePending(tstate);
    }
    return 0;
}

static inline int
check_periodics_at_end(PyThreadState *tstate, _PyInterpreterFrame *frame) {
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        if (frame->instr_ptr[-1].op.code == LOAD_SPECIAL) {
            return 0;
        }
        return _Py_HandlePending(tstate);
    }
    return 0;
}
```

### TimeGuard-PVM Modified Code:
```c
/* =========================================================================
 * [TimeGuard-PVM]: Inlined fast tick check
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
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        return _Py_HandlePending(tstate);
    }
    return 0;
}

static inline int
check_periodics_at_end(PyThreadState *tstate, _PyInterpreterFrame *frame) {
    /* [TimeGuard-PVM]: First check the execution deadline */
    if (_Py_TimeGuard_Check(tstate) != 0) {
        return -1;
    }
    _Py_CHECK_EMSCRIPTEN_SIGNALS_PERIODICALLY();
    QSBR_QUIESCENT_STATE(tstate);
    if (_Py_atomic_load_uintptr_relaxed(&tstate->eval_breaker) & _PY_EVAL_EVENTS_MASK) {
        if (frame->instr_ptr[-1].op.code == LOAD_SPECIAL) {
            return 0;
        }
        return _Py_HandlePending(tstate);
    }
    return 0;
}
```

### 💡 Why this was changed:
- **`check_periodics`** is called by `JUMP_BACKWARD` (on every loop iteration) and `RESUME`.
- **`check_periodics_at_end`** is called by `CALL` (on every function invocation).
- By inserting `_Py_TimeGuard_Check` here:
  - If budget is disabled (`<= 0`), it costs a single integer comparison (<0.1 nanosecond).
  - If budget is active, `(++ticks & 0xFF) != 0` skips the clock query 255 out of 256 times.
  - On the 256th tick, `clock_gettime()` is called. If expired, returning `-1` jumps directly to CPython's exception unwinding path (`JUMP_TO_LABEL(error)`).

---

## Site 4: `Python/sysmodule.c` (Python `sys.set/get_time_budget_ms` API)

### Original CPython Code:
```c
static PyMethodDef sys_methods[] = {
    /* Might as well keep this in alphabetic order */
    SYS_ADDAUDITHOOK_METHODDEF
    SYS_AUDIT_METHODDEF
...

static PyStatus
_PySys_InitCore(PyThreadState *tstate, PyObject *sysdict)
{
    PyObject *version_info;
    int res;
    PyInterpreterState *interp = tstate->interp;
```

### TimeGuard-PVM Modified Code:
```c
/* =========================================================================
 * [TimeGuard-PVM]: sys.set_time_budget_ms and sys.get_time_budget_ms
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

static PyMethodDef sys_methods[] = {
    {"set_time_budget_ms", sys_set_time_budget_ms, METH_VARARGS, "set_time_budget_ms(ms) -> Set execution time budget in milliseconds (0 to disable)."},
    {"get_time_budget_ms", sys_get_time_budget_ms, METH_NOARGS, "get_time_budget_ms() -> Get current execution time budget in milliseconds."},
    /* Might as well keep this in alphabetic order */
    SYS_ADDAUDITHOOK_METHODDEF
    SYS_AUDIT_METHODDEF
...

static PyStatus
_PySys_InitCore(PyThreadState *tstate, PyObject *sysdict)
{
    /* [TimeGuard-PVM]: Initialize budget from TIMEGUARD_MS environment variable */
    _Py_TimeGuard_Init();

    PyObject *version_info;
    int res;
    PyInterpreterState *interp = tstate->interp;
```

### 💡 Why this was changed:
- Exposes `sys.set_time_budget_ms(ms)` and `sys.get_time_budget_ms()` directly into Python user space without requiring external C extensions.
- Initializes the `TIMEGUARD_MS` environment variable early in the interpreter lifecycle (`_PySys_InitCore`).

---

## Site 5: `Python/getversion.c` (Version Banner Branding)

### Original CPython Code:
```c
#ifdef Py_GIL_DISABLED
    const char *buildinfo_format = "%.80s free-threading build (%.80s) %.80s";
#else
    const char *buildinfo_format = "%.80s (%.80s) %.80s";
#endif
```

### TimeGuard-PVM Modified Code:
```c
#ifdef Py_GIL_DISABLED
    /* [TimeGuard-PVM]: Branded version banner */
    const char *buildinfo_format = "%.80s free-threading build [TimeGuard-PVM] (%.80s) %.80s";
#else
    /* [TimeGuard-PVM]: Branded version banner */
    const char *buildinfo_format = "%.80s [TimeGuard-PVM] (%.80s) %.80s";
#endif
```

### 💡 Why this was changed:
- Cleanly identifies the custom runtime in `sys.version` and the interactive REPL banner (e.g., `3.16.0a2+dev [TimeGuard-PVM]`).

---

## Site 6: `Lib/platform.py` (Version Parser Compatibility)

### Original CPython Code:
```python
        # CPython
        cpython_sys_version_parser = re.compile(
            r'([\w.+]+)\s*'  # "version<space>"
            r'(?:free-threading build\s+)?' # "free-threading-build<space>"
            r'\(#?([^,]+)'  # "(#buildno"
            r'(?:,\s*([\w ]*)'  # ", builddate"
            r'(?:,\s*([\w :]*))?)?\)\s*'  # ", buildtime)<space>"
            r'\[([^\]]+)\]?', re.ASCII)  # "[compiler]"
```

### TimeGuard-PVM Modified Code:
```python
        # CPython
        cpython_sys_version_parser = re.compile(
            r'([\w.+]+)\s*'  # "version<space>"
            r'(?:free-threading build\s+)?' # "free-threading-build<space>"
            # [TimeGuard-PVM]: Allow [TimeGuard-PVM] tag in version parser
            r'(?:\[TimeGuard-PVM\]\s+)?'
            r'\(#?([^,]+)'  # "(#buildno"
            r'(?:,\s*([\w ]*)'  # ", builddate"
            r'(?:,\s*([\w :]*))?)?\)\s*'  # ", buildtime)<space>"
            r'\[([^\]]+)\]?', re.ASCII)  # "[compiler]"
```

### 💡 Why this was changed:
- Python's standard `platform` module parses `sys.version` using strict regex patterns.
- Adding `(?:\[TimeGuard-PVM\]\s+)?` ensures that `platform.python_version()`, `pip`, and `ensurepip` continue to parse the version string cleanly without raising `ValueError`.
