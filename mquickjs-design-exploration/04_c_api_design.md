# mquickjs: C API Design

## Introduction

The C API of `mquickjs` is designed for embedding in resource-constrained environments. It prioritizes explicit memory control (via the provided buffer) and minimal dependency on the host OS.

## Core Concepts

### 1. The Context (`JSContext`)
Unlike QuickJS which has a `JSRuntime` (global) and multiple `JSContext`s, `mquickjs` simplifies this. The `JSContext` is the main handle, initialized with a fixed memory buffer.

```c
uint8_t mem_buf[8192];
JSContext *ctx = JS_NewContext(mem_buf, sizeof(mem_buf), &js_stdlib);
```

### 2. Value Handling
*   **By Value**: `JSValue` is passed by value (it's a 32/64-bit integer/struct).
*   **No Explicit Free**: A major shift from QuickJS. Since the GC is compacting and tracing, the user does not call `JS_FreeValue`.
*   **GC Refs**: As explained in the Memory section, users must use `JS_PushGCRef` / `JS_PopGCRef` to hold references that survive across allocations, because the GC might move objects.

### 3. Error Handling
*   **Exception Value**: Functions return `JS_EXCEPTION` (a tagged value) on error.
*   **Check**: `JS_IsException(val)` is used to check for errors.
*   **Get Exception**: `JS_GetException(ctx)` retrieves the actual error object.

## Standard Library Definition (`JSSTDLibraryDef`)
To support the "ROMable" feature, the standard library is passed as a constant structure `JSSTDLibraryDef`.

```c
typedef struct {
    const JSWord *stdlib_table;        // Serialized objects
    const JSCFunctionDef *c_function_table; // C functions implementation
    ...
} JSSTDLibraryDef;
```
This allows the engine to be generic, while the specific environment (stdlib) is injected at creation time.

### Meta Image: API Interaction Model
[META IMAGE DESCRIPTION]
A diagram showing the interaction flow between C code and mquickjs.
1.  **Init**: C code allocates buffer -> calls `JS_NewContext` -> receives `ctx`.
2.  **Call JS**: C code calls `JS_Eval(ctx, code)` -> receives `JSValue` result.
3.  **Call C**: JS code calls function -> Engine looks up `c_function_table` -> invokes C callback.
4.  **Error Loop**: `JSValue` result checked with `JS_IsException`. If true, `JS_GetException` called.
[/META IMAGE DESCRIPTION]

## Design Patterns Noted
*   **Inversion of Control (Memory)**: The library doesn't ask for memory; it is told what memory to use.
*   **Static Configuration**: Heavy use of `const` structures (`JSSTDLibraryDef`) to allow placing configuration in ROM (Flash).
*   **Opaque Handles**: `JSGCRef` provides an opaque handle to a moving target, solving the stale pointer problem in a compacting GC.
