# mquickjs: Integration & System Interaction

## Introduction

mquickjs is designed to be deeply integrated into the host system with minimal friction. Its "ROMable" nature and lack of OS dependencies make it unique. This section covers how it handles the Standard Library, Modules, and the specific design patterns Bellard uses to achieve this.

## The Standard Library: "Frozen" in ROM

The most striking integration pattern is how the standard library is handled. Instead of initializing the JS environment by running JS code or making thousands of C API calls at runtime (which consumes RAM and CPU), mquickjs **compiles the standard library definition into C data structures**.

### The Build Process (Meta-Compilation)
1.  **Definition**: `mqjs_stdlib.c` defines the classes, methods, and properties using C macros (`JS_CLASS_DEF`, `JS_CFUNC_DEF`).
2.  **Extraction**: The `mquickjs_build` tool compiles this C file and inspects the structures.
3.  **Generation**: It outputs `mqjs_stdlib.h`, which contains:
    *   **Bytecode**: For any JS implementation details.
    *   **Property Tables**: Hash tables pre-calculated for the ROM.
    *   **Atom Tables**: All string literals used by the stdlib are pre-interned.

This means when `JS_NewContext` is called, the "Global Object" is mostly just a pointer to this read-only data.

## Module Loading

QuickJS (the parent project) has a complex module loader. mquickjs simplifies this. Code is typically loaded as a script. `mqjs.c` shows how to load bytecode or source text.
*   **Source**: `JS_Eval` parses and executes.
*   **Bytecode**: `JS_LoadBytecode` / `JS_Run`.

## Bellardian Design Patterns

Fabrice Bellard's codebases share distinctive traits found here:

### 1. Zero-Dependency Re-implementation
The project includes `libm.c` (Math), `dtoa.c` (Double-to-String), and `cutils.c` (Strings/Lists).
*   **Why**: Guarantees identical behavior across all platforms (embedded, Linux, Windows) and avoids bloat from standard `libc` implementations.
*   **Pattern**: "Own the whole stack" for reliability and size.

### 2. Macro Metaprogramming
The `mquickjs_build.h` uses macros to define data structures that are later "reflected" upon by the build tool.
```c
#define JS_CLASS_DEF(...) { __VA_ARGS__ }
```
This allows writing the standard library in a declarative C syntax that looks almost like a DSL.

### 3. Container_of and Intrusive Lists
`list.h` implements intrusive doubly-linked lists.
*   **Intrusive**: The `struct list_head` is embedded *inside* the object (e.g., `JSRuntime`, `JSContext`).
*   **Container_of**: The macro `container_of` is used to recover the parent object pointer from the list node pointer. This avoids separate memory allocations for list nodes.

### 4. Single-Header / Single-Source Philosophy
While split into a few files, `mquickjs.c` is the "unity build" of the engine. It includes `mquickjs_opcode.h` and others. This encourages the compiler to inline aggressively across what would normally be translation unit boundaries.

### Meta Image: Build Pipeline
[META IMAGE DESCRIPTION]
A pipeline diagram showing the "Frozen Standard Library" creation.
1.  **Input**: `mqjs_stdlib.c` (Declarative C Macros).
2.  **Tool**: `mquickjs_build` (Meta-compiler).
3.  **Output**: `mqjs_stdlib.h` (Generated C Arrays & Structs).
4.  **Final Build**: `mquickjs.c` `#include`s `mqjs_stdlib.h` -> `mquickjs.o` -> `mqjs` Executable.
[/META IMAGE DESCRIPTION]

## Conclusion on Integration
mquickjs integrates by **becoming part of the application's binary** rather than acting as a dynamic library. The state is largely static (ROM), and the dynamic part is strictly confined to the user-provided memory buffer.
