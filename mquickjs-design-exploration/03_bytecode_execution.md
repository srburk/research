# mquickjs: Bytecode Generation & Execution

## Introduction

mquickjs uses a stack-based bytecode interpreter. Code is compiled in a single pass directly to bytecode, skipping an explicit Abstract Syntax Tree (AST) to save memory. The execution model relies on a main loop `JS_Call` that dispatches opcodes.

## The Compiler (Parser)

*   **Single Pass**: The parser (`js_parse`) reads tokens and emits bytecode immediately.
*   **No AST**: This drastically reduces memory usage during compilation but makes complex optimizations harder.
*   **Recursion Avoidance**: The parser is written to avoid deep recursion on the C stack, instead managing its own state where possible (though `js_parse_expr` still seems recursive in structure, the `README` claims it avoids recursion - likely meaning for statements or specific constructs).
*   **Bytecode**: The output is a `JSFunctionBytecode` object containing the `JSByteArray` of instructions and a constant pool.

## The Execution Loop (`JS_Call`)

The heart of the engine is `JS_Call`. It serves as both the entry point for function calls and the main interpreter loop.

*   **Interpreter Loop**: A massive `for(;;) { switch(*pc++) { ... } }` loop handles instruction dispatch.
*   **Stack-Based**: Instructions push/pop values from the stack pointer `sp`.
*   **Computed Gotos**: Not explicitly seen in the code (standard `switch` used), but the structure allows for it if the compiler optimizes.
*   **Unified Stack**: The C stack is used for the interpreter's recursion (calling `JS_Call`), but the JS values live on a separate value stack managed by `ctx->sp`.
*   **Recursion Limit**: `JS_MAX_CALL_RECURSE` protects against C stack overflow.

### Meta Image: Execution Flow
[META IMAGE DESCRIPTION]
A flowchart describing the `JS_Call` execution loop.
1.  **Start**: `JS_Call(ctx, call_flags)` called.
2.  **Setup**: Initialize `sp` (stack pointer), `fp` (frame pointer), and `pc` (program counter).
3.  **Dispatch Loop**:
    *   Fetch opcode at `pc`.
    *   Increment `pc`.
    *   **Switch (opcode)**:
        *   **Arithmetic (ADD, SUB)**: Pop operands, compute, push result.
        *   **Control Flow (GOTO, IF)**: Update `pc`.
        *   **Function Call (CALL)**:
            *   Push arguments and `this`.
            *   Update `fp`.
            *   `goto function_call` (internal label) to restart loop for new function WITHOUT C recursion (tail-call optimization for JS functions).
            *   OR recursively call `JS_Call` for C functions or complex cases.
4.  **Return**: Restore previous `fp`, push return value, continue.
[/META IMAGE DESCRIPTION]

## Optimization Patterns

1.  **Direct Goto for Calls**: When a JS function calls another JS function, the engine tries to update the state (`fp`, `pc`) and jump to `function_call` label instead of recursively calling `JS_Call` in C. This is a form of **threaded interpreter** optimization to reduce C stack usage.
2.  **Short Opcodes**: Frequent operations (pushing small integers `0`, `1`, `-1`) have dedicated 1-byte opcodes (`OP_push_0`, etc.) to reduce bytecode size.
3.  **Pre-allocated Objects**: `OP_object` takes a size hint to pre-allocate the hash table, avoiding resizing during object literal creation.

## Design Patterns Noted
*   **Bytecode-as-IR**: Using bytecode as the primary Intermediate Representation instead of an AST is a classic "Bellard" move for compactness.
*   **Label-based Dispatch**: Using `goto` labels within the interpreter (`function_call`, `c_function`) allows handling transitions between JS functions efficiently within a single C function stack frame.
