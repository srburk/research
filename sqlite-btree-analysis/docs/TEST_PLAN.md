# B-Tree Indexing Test Plan

## Overview

This document outlines the comprehensive test plan for validating the B-tree implementation and measuring performance metrics that demonstrate how B-trees accelerate database indexing.

## Test Categories

### 1. Unit Tests (Correctness)

#### 1.1 Basic Operations

| Test ID | Description | Expected Result | Priority |
|---------|-------------|-----------------|----------|
| UT-001 | Create and destroy empty tree | No memory leaks, clean shutdown | High |
| UT-002 | Insert single key | Key found on search | High |
| UT-003 | Insert multiple keys | All keys found | High |
| UT-004 | Search non-existent key | Returns NOT_FOUND | High |
| UT-005 | Update existing key | Value updated | Medium |
| UT-006 | Delete key | Key not found after delete | Medium |

#### 1.2 Edge Cases

| Test ID | Description | Expected Result | Priority |
|---------|-------------|-----------------|----------|
| EC-001 | Empty tree operations | Graceful handling | High |
| EC-002 | Single node tree | Correct behavior | High |
| EC-003 | Full node split | Tree remains valid | High |
| EC-004 | Minimum order tree (order=3) | Correct operation | Medium |
| EC-005 | Maximum order tree (order=1024) | Correct operation | Medium |
| EC-006 | Duplicate key insertion | Handle gracefully | Medium |

#### 1.3 Stress Tests

| Test ID | Description | Expected Result | Priority |
|---------|-------------|-----------------|----------|
| ST-001 | Insert 10,000 sequential keys | Tree valid, all found | High |
| ST-002 | Insert 10,000 random keys | Tree valid, all found | High |
| ST-003 | Insert 100,000 keys | Completes in reasonable time | Medium |
| ST-004 | Mixed insert/search workload | Correct results | High |

### 2. Performance Benchmarks

#### 2.1 Scaling Analysis

**Objective**: Verify O(log N) search complexity

| Test ID | Dataset Size | Metric | Expected Range |
|---------|-------------|--------|----------------|
| PB-001 | 1,000 | Avg comparisons | 10-15 |
| PB-002 | 10,000 | Avg comparisons | 14-20 |
| PB-003 | 100,000 | Avg comparisons | 18-25 |
| PB-004 | 1,000,000 | Avg comparisons | 21-30 |

**Validation Criteria**:
- Comparisons should grow logarithmically
- Doubling data size should add ~7 comparisons (log2 factor)
- Tree height should match ceil(log_order(N))

#### 2.2 Order (Fanout) Impact

**Objective**: Determine optimal B-tree order

| Test ID | Order | Expected Height (N=100K) | Trade-off |
|---------|-------|-------------------------|-----------|
| PO-001 | 4 | ~8-9 | Deep tree, fast node search |
| PO-002 | 16 | ~4-5 | Balanced |
| PO-003 | 64 | ~3 | Shallow, slower node search |
| PO-004 | 256 | ~2-3 | Very shallow |

**Validation Criteria**:
- Height = ceil(log_order(N))
- Optimal throughput typically at order 64-256

#### 2.3 B-tree vs Linear Comparison

**Objective**: Quantify B-tree performance advantage

| Test ID | Dataset Size | B-tree Comparisons | Linear Comparisons | Speedup |
|---------|-------------|-------------------|-------------------|---------|
| CMP-001 | 1,000 | ~10 | ~500 | ~50x |
| CMP-002 | 10,000 | ~14 | ~5,000 | ~350x |
| CMP-003 | 100,000 | ~17 | ~50,000 | ~2,900x |

**Validation Criteria**:
- B-tree comparisons should be O(log N)
- Linear comparisons should be O(N)
- Speedup should increase with data size

### 3. Cursor Tests

| Test ID | Description | Expected Result | Priority |
|---------|-------------|-----------------|----------|
| CR-001 | Iterate forward through all keys | Keys in sorted order | High |
| CR-002 | Iterate backward | Keys in reverse order | Medium |
| CR-003 | Cursor on empty tree | Invalid cursor | Medium |
| CR-004 | Cursor after modifications | Handles gracefully | Medium |

### 4. Validation Tests

| Test ID | Description | Expected Result | Priority |
|---------|-------------|-----------------|----------|
| VL-001 | Keys sorted within nodes | All nodes pass | High |
| VL-002 | Key count bounds | Within min/max | High |
| VL-003 | Child pointer consistency | All valid | High |
| VL-004 | No cycles in tree | Acyclic | High |

## Test Execution

### Running Unit Tests

```bash
# Build and run all unit tests
make test

# Expected output:
# ╔══════════════════════════════════════════════════════════════════╗
# ║                   B-TREE UNIT TEST SUITE                         ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# Running: Create and Destroy
#   [PASS] test_create_destroy
# Running: Single Insert and Search
#   [PASS] test_single_insert_search
# ... (all tests)
#
# Results: 16/16 tests passed
# *** ALL TESTS PASSED ***
```

### Running Performance Benchmarks

```bash
# Run full benchmark suite
make benchmark

# Save results for analysis
./build/btree_benchmark > benchmark_results/benchmark_results.txt

# Analyze results
python3 tests/generate_tests.py --analyze benchmark_results/benchmark_results.txt
```

### Running Python Test Generator

```bash
# Generate test data
python3 tests/generate_tests.py --generate --output tests/data --seed 42

# Validate complexity
python3 tests/generate_tests.py --validate benchmark_results/benchmark_results.txt
```

## Acceptance Criteria

### Correctness Criteria

1. **All unit tests pass** (16/16)
2. **Tree validation passes** after all operations
3. **No memory leaks** (check with valgrind)
4. **All inserted keys are found** on search
5. **Non-existent keys return NOT_FOUND**

### Performance Criteria

1. **Search complexity is O(log N)**:
   - Comparisons per search < 2 * log2(N) for typical orders
   - Tree height ≤ ceil(log_order(N))

2. **Insert throughput**:
   - Sequential: > 500,000 ops/sec
   - Random: > 100,000 ops/sec

3. **Search throughput**:
   - > 1,000,000 ops/sec for in-memory trees

4. **B-tree vs Linear advantage**:
   - At N=100,000: B-tree > 2000x faster

### Quality Criteria

1. **Fill factor**: 50-80% average
2. **Height efficiency**: Within theoretical bounds
3. **Memory usage**: Proportional to key count

## Test Data

### Test Data Characteristics

| Dataset | Size | Pattern | Use Case |
|---------|------|---------|----------|
| Sequential | 1K-1M | 1, 2, 3, ... | Worst-case for some trees |
| Random | 1K-1M | Uniform random | Average case |
| Skewed | 1K-1M | Zipfian | Real-world simulation |
| Shuffled | 1K-1M | Sequential then shuffled | Best-case for B-trees |

### Generating Test Data

```python
# From Python test generator
from tests.generate_tests import TestDataGenerator

generator = TestDataGenerator(seed=42)
sequential = generator.generate_sequential_keys(10000)
random_keys = generator.generate_random_keys(10000)
skewed = generator.generate_skewed_keys(10000, skew_factor=0.8)
```

## Reporting

### Benchmark Report Format

```
BENCHMARK 1: Scaling Analysis
Shows how B-tree performance scales with data size
═══════════════════════════════════════════════════

Records    | Height | Avg Comparisons | Theoretical
-----------|--------|-----------------|-------------
1,000      | 2      | 12.5            | 14.0
10,000     | 2      | 14.2            | 14.0
100,000    | 3      | 19.8            | 21.0
1,000,000  | 4      | 25.1            | 28.0

Conclusion: B-tree demonstrates O(log N) search complexity ✓
```

### Success/Failure Criteria

| Category | Pass Condition |
|----------|----------------|
| Unit Tests | 100% pass rate |
| Performance | Within 20% of expected |
| Complexity | O(log N) validated |
| Memory | No leaks detected |

## Test Environment

### Minimum Requirements

- **OS**: Linux (Ubuntu 20.04+), macOS 10.15+, or WSL
- **Compiler**: GCC 9+ or Clang 10+
- **Memory**: 1GB free RAM for large tests
- **Python**: 3.8+ for test generation

### Recommended Setup

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install build-essential python3 python3-pip

# Verify
gcc --version
python3 --version

# Build project
make clean && make all
```

## Appendix: Theoretical Background

### B-tree Complexity Analysis

For a B-tree of order `m` with `N` keys:

- **Height**: h = ceil(log_m(N))
- **Search comparisons**: O(h * log2(m)) = O(log N)
- **Node visits**: h = O(log_m(N))

### SQLite Reference Values

From SQLite's btreeInt.h:
- Default page size: 4096 bytes
- Typical order: ~100-200 (based on page size and key size)
- Maximum depth: 20 levels (BTCURSOR_MAX_DEPTH)
- Maximum database: 2^31 pages

### Expected Performance Characteristics

| Metric | Sequential Insert | Random Insert | Search |
|--------|------------------|---------------|--------|
| Complexity | O(N log N) total | O(N log N) total | O(log N) |
| Page reads | 1-2 per insert | 2-4 per insert | h pages |
| Comparisons | ~log2(m) per node | ~log2(m) per node | h * log2(m) |
