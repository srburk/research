# mquickjs: Memory Management & Garbage Collection

## Introduction

Memory management in `mquickjs` is a radical departure from the original QuickJS. While QuickJS uses reference counting with cycle detection, `mquickjs` uses a **tracing and compacting garbage collector**. This choice is driven by the goal of minimizing RAM usage and handling memory fragmentation in constrained environments (embedded systems).

## JSValue Representation

`JSValue` is the fundamental type for representing JavaScript values. It is optimized to fit in a single CPU word (32-bit or 64-bit).

*   **Size**: Same as CPU word (32-bit on 32-bit arch, 64-bit on 64-bit arch).
*   **Tagging Strategy**: Tagged Union / NaN Boxing variant.
    *   **Integers**: 31-bit integers are stored directly with a 1-bit tag (e.g., `val | 0` vs `val | 1`).
    *   **Pointers**: Stored with a tag indicating it points to the heap.
    *   **Special Values**: Null, Undefined, True, False are encoded with specific tag combinations.
    *   **Floats**: 64-bit floats are supported but obviously cannot fit entirely in a 32-bit value. They are likely allocated on the heap or represented specially if the architecture allows (softfloat).

### Meta Image: JSValue Layout
[META IMAGE DESCRIPTION]
A diagram showing the bit layout of a 32-bit `JSValue`.
- **Bits 0-30**: Payload (Integer value or Pointer offset).
- **Bit 31 (Tag)**:
    - `0`: Integer.
    - `1`: Pointer/Special.
    - If Pointer/Special, secondary bits (e.g., bits 0-2) might differentiate between Ptr, Null, Undefined.
- **Visual Note**: Show two rows, one for "Immediate Integer" and one for "Heap Pointer".
[/META IMAGE DESCRIPTION]

## The Allocator

There is no dependence on system `malloc`/`free`. The user must provide a contiguous block of memory at initialization (`JS_NewContext`).

*   **Linear Allocation**: The engine manages this block.
*   **Structure**: The heap is likely a linked list of blocks or a compactable region.
*   **No Explicit Free**: Users of the C API do not call `JS_FreeValue`. The GC handles everything.

## Garbage Collection (GC)

The GC is **Tracing** and **Compacting**.

### 1. Tracing (Mark Phase)
The GC starts from "roots" and recursively marks all reachable objects.
*   **Roots**:
    *   Global variables.
    *   The C stack (this is tricky in portable C, `mquickjs` handles this by requiring explicit root registration via `JS_PushGCRef` or by scanning the stack if conservative - though `mquickjs` seems to require explicit refs).
    *   Internal VM registers.

### 2. Compacting (Sweep & Move Phase)
This is the critical differentiator.
*   **Compaction**: Reachable objects are moved to one end of the heap to eliminate fragmentation.
*   **Pointer Updates**: Since objects move, all pointers to them must be updated. This is why the C API requires `JSGCRef`.
*   **JSGCRef**: A handle system. The C code holds a handle (`JSGCRef`), and the engine updates the value inside the handle when the object moves.

```c
/* Example of safe handle usage */
JSValue my_func(JSContext *ctx) {
    JSGCRef obj_ref;
    JSValue *obj = JS_PushGCRef(ctx, &obj_ref); /* Register root */
    *obj = JS_NewObject(ctx);
    /* Allocation of another object might trigger GC and move *obj */
    JSValue other = JS_NewObject(ctx);
    /* *obj is still valid because JS_PushGCRef registered it */
    JS_PopGCRef(ctx, &obj_ref);
    return other;
}
```

### Meta Image: Compacting GC
[META IMAGE DESCRIPTION]
A 3-step diagram illustrating the Compacting GC.
1.  **Before GC**: Memory buffer with scattered objects (A, B, C) and gaps (free space).
2.  **Mark**: Objects A and C are marked as reachable. B is unreachable.
3.  **Compact**: A and C are moved to the start of the buffer, contiguous. B is overwritten. The free pointer is updated to the end of C. All references to A and C are updated to new addresses.
[/META IMAGE DESCRIPTION]

## Design Patterns Noted
*   **Handle Pattern**: Using `JSGCRef` to solve the "dangling pointer due to relocation" problem.
*   **Arena/Region Allocation**: The user-supplied buffer acts as a single arena, simplifying resource cleanup (just drop the buffer).
*   **Tagged Pointers**: Heavy use of bit manipulation to squeeze types into 32 bits.
