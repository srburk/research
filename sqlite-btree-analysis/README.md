# SQLite B-Tree Indexing Analysis

A comprehensive analysis of SQLite's B-tree indexing mechanism with a working C implementation, performance benchmarks, and test suite.

## Overview

This project provides:

1. **Architecture Documentation**: In-depth analysis of SQLite's B-tree implementation based on actual source code review
2. **C Implementation**: A working B-tree implementation demonstrating key concepts
3. **Performance Benchmarks**: Measurable metrics comparing B-tree vs linear search
4. **Test Suite**: Unit tests and Python-based test data generator

## Project Structure

```
sqlite-btree-analysis/
├── README.md                    # This file
├── Makefile                     # Build configuration
├── docs/
│   └── ARCHITECTURE.md          # Comprehensive architecture analysis
├── src/
│   ├── btree.h                  # B-tree API header
│   ├── btree.c                  # B-tree implementation
│   └── benchmark.c              # Performance benchmark suite
├── tests/
│   ├── test_btree.c             # C unit tests
│   └── generate_tests.py        # Python test generator
└── benchmark_results/           # Benchmark output directory
```

## Quick Start

### Prerequisites

- **GCC compiler** (or compatible C11 compiler)
- **Make** build tool
- **Python 3** (for test generation and analysis)
- **UNIX-like environment** (Linux, macOS, or WSL)

### Build and Run

```bash
# Clone or navigate to the project
cd sqlite-btree-analysis

# Build the benchmark
make

# Run the full benchmark suite
make benchmark

# Run unit tests
make test

# Generate test data with Python
python3 tests/generate_tests.py --generate
```

## Build Instructions

### Standard Build

```bash
# Compile with optimizations
make all

# The executable will be at build/btree_benchmark
./build/btree_benchmark
```

### Debug Build

```bash
# Build with debug symbols (no optimization)
make debug

# Run with gdb for debugging
gdb ./build/btree_benchmark
```

### Clean Build

```bash
# Remove build artifacts
make clean

# Remove everything including results
make distclean
```

## Running Benchmarks

### Full Benchmark Suite

```bash
make benchmark
```

This runs all benchmark tests and saves results to `benchmark_results/benchmark_results.txt`.

### Understanding Benchmark Output

The benchmark outputs metrics in a table format:

| Metric | Description |
|--------|-------------|
| Records | Number of records in the test |
| Order | B-tree order (max children per node) |
| Insert(ms) | Time to insert all records |
| Insert/sec | Insertion throughput |
| Search/sec | Search throughput |
| Height | Resulting tree height |
| Avg Cmp | Average comparisons per search |
| Avg Node | Average node visits per search |
| Fill% | Node fill factor |

### Benchmark Suites

The benchmark includes 5 test suites:

1. **Scaling Analysis**: How performance scales with data size (1K to 1M records)
2. **Order Comparison**: Impact of B-tree order on performance
3. **B-tree vs Linear**: Comparison with linear search (O(log n) vs O(n))
4. **Insertion Pattern**: Sequential vs random insertion patterns
5. **Theoretical Validation**: Verification of O(log n) complexity

## Test Plan

### Unit Tests (C)

Run the C unit test suite:

```bash
make test
```

Tests include:
- Basic operations (insert, search, delete)
- Edge cases (empty tree, single node, duplicates)
- Stress tests (10,000+ records)
- Cursor iteration
- Tree validation

### Test Data Generation (Python)

Generate test data for additional testing:

```bash
# Generate test data files
python3 tests/generate_tests.py --generate --output tests/data

# Analyze benchmark results
python3 tests/generate_tests.py --analyze benchmark_results/benchmark_results.txt

# Validate O(log n) complexity
python3 tests/generate_tests.py --validate benchmark_results/benchmark_results.txt
```

### Manual Testing

You can manually verify B-tree behavior:

```bash
# Build and run
make
./build/btree_benchmark

# Check output for:
# 1. Tree height growing logarithmically with data size
# 2. B-tree being significantly faster than linear search
# 3. Fill factor between 50-100%
# 4. Comparisons per search matching theoretical expectations
```

## Performance Expectations

### Expected Results

Based on B-tree theory and SQLite's implementation:

| Records | Expected Height (Order=128) | Expected Comparisons |
|---------|----------------------------|----------------------|
| 1,000 | 2 | ~14 |
| 10,000 | 2-3 | ~14-21 |
| 100,000 | 3 | ~21 |
| 1,000,000 | 3-4 | ~21-28 |

### B-tree vs Linear Search

For 100,000 records:
- **B-tree**: ~21 comparisons per search
- **Linear**: ~50,000 comparisons per search (average)
- **Speedup**: ~2,380x fewer comparisons

### Key Observations

1. **Logarithmic Growth**: Tree height grows as O(log_order(N))
2. **High Fanout Matters**: Order of 64-256 provides optimal balance
3. **Fill Factor**: Typically 50-75% after random insertions
4. **Constant Time per Level**: Binary search within each node

## API Reference

### Core Functions

```c
// Create a B-tree with specified order
btree_t* btree_create(uint32_t order);

// Insert a key-value pair
btree_status_t btree_insert(btree_t *tree, btree_key_t key, btree_value_t value);

// Search for a key
btree_status_t btree_search(btree_t *tree, btree_key_t key, btree_value_t *value);

// Check if key exists
bool btree_contains(btree_t *tree, btree_key_t key);

// Get tree statistics
btree_stats_t btree_stats_get(btree_t *tree);

// Destroy the tree
void btree_destroy(btree_t *tree);
```

### Cursor Operations

```c
// Create a cursor for iteration
btree_cursor_t* btree_cursor_create(btree_t *tree);

// Move to first/last element
btree_status_t btree_cursor_first(btree_cursor_t *cursor);
btree_status_t btree_cursor_last(btree_cursor_t *cursor);

// Navigate
btree_status_t btree_cursor_next(btree_cursor_t *cursor);
btree_status_t btree_cursor_prev(btree_cursor_t *cursor);

// Get current key/value
btree_status_t btree_cursor_get(btree_cursor_t *cursor, btree_key_t *key, btree_value_t *value);
```

## Architecture Highlights

See `docs/ARCHITECTURE.md` for detailed analysis. Key points:

### SQLite B-tree Design

- Uses B+trees for table data (data only at leaves)
- Uses standard B-trees for indexes
- Page size: 512 bytes to 64KB (default 4KB)
- Maximum tree depth: 20 levels
- Binary search within nodes

### Performance Characteristics

- **Search**: O(log N) - typically 3-5 page reads
- **Insert**: O(log N) with node splitting
- **Range scan**: O(log N + K) where K is result size
- **Space efficiency**: ~70% average fill factor

## Troubleshooting

### Build Issues

```bash
# If make fails, check for GCC
gcc --version

# On Ubuntu/Debian, install build essentials
sudo apt-get install build-essential

# On macOS, install Xcode command line tools
xcode-select --install
```

### Runtime Issues

```bash
# If benchmark crashes on large datasets, check memory
ulimit -s unlimited  # Increase stack size

# For timing issues, ensure system isn't under load
nice -n -10 ./build/btree_benchmark
```

## References

- SQLite Source Code: https://github.com/sqlite/sqlite
- SQLite File Format: https://www.sqlite.org/fileformat.html
- Knuth, D.E. "The Art of Computer Programming, Volume 3"

## License

This project is for educational and research purposes. The B-tree implementation is original work. SQLite references are for analysis purposes only.
