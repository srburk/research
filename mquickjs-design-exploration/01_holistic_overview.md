# mquickjs: Holistic Overview

## Introduction

mquickjs is a tiny, embeddable JavaScript engine written by Fabrice Bellard and Charlie Gordon. It is a derivative of QuickJS, optimized for even smaller footprints and different architectural goals, specifically targeting embedded systems (ROMable) and strict memory limits.

Key design philosophies observed:
*   **Minimalism**: Zero dependencies on system `malloc`/`free`. Uses a compacting GC instead of Reference Counting (mostly).
*   **Embeddability**: The standard library and bytecode can be compiled into ROM, significantly reducing RAM usage and startup time.
*   **Performance**: Optimized for size and speed on small CPUs (32-bit values).

## Directory Structure

*   `mquickjs.c / .h`: The core Javascript engine.
*   `mquickjs_priv.h`: Internal structures and definitions.
*   `mqjs.c`: The command-line interpreter (the REPL and script runner).
*   `libm.c`: A tiny implementation of the C math library, ensuring self-containedness.
*   `mqjs_stdlib.c`: The definition of the standard library, which gets compiled into C headers.
*   `mquickjs_build.c`: A "meta-compiler" tool that generates C headers (`mqjs_stdlib.h`) from JS standard library definitions.

## Build System Architecture

The build system uses a standard `Makefile` but employs an interesting 2-stage process for the standard library:

1.  **Meta-Compilation**: `mquickjs_build.c` is compiled to a host executable (`mqjs_stdlib`).
2.  **Generation**: `mqjs_stdlib` is run to process `mqjs_stdlib.c` and generate `mqjs_stdlib.h`.
3.  **Compilation**: `mquickjs.c` includes the generated header, baking the standard library directly into the engine's binary.

This "bootstrapping" phase allows complex JS initialization logic to be pre-computed and stored in read-only memory (ROM).

## High-Level Architecture

The system revolves around a `JSRuntime` (global state) and `JSContext` (execution context). Unlike larger engines, memory management is tightly controlled via a contiguous memory buffer provided by the user.

### Meta Image: System Architecture
[META IMAGE DESCRIPTION]
A block diagram illustrating the mquickjs architecture.
- **Top Layer**: User Application (embedder).
- **Middle Layer (mquickjs)**:
    - **API Surface**: `quickjs.h` functions.
    - **Core Engine**: `mquickjs.c` (Interpreter, GC, Parser).
    - **Memory Manager**: Manages the user-provided "Memory Buffer".
- **Bottom Layer**:
    - **ROM**: Contains `mqjs_stdlib` (Standard Library definitions) and Bytecode.
    - **RAM**: Dynamic allocations (Objects, Strings) happen here inside the buffer.
- **Arrows**:
    - User Application calls API Surface.
    - Core Engine reads from ROM and allocates in RAM.
[/META IMAGE DESCRIPTION]

## Design Patterns Noted
*   **Amalgamation**: Core logic is concentrated in `mquickjs.c` for easier inclusion and optimization.
*   **Zero-dependency**: Re-implementation of standard utilities (`libm`, `dtoa`) to ensure consistent behavior across platforms.
*   **Pre-computation**: Heavy reliance on build-time generation to reduce runtime cost (atoms, standard library).
