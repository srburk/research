# B-Tree Indexing Performance Analysis
# Makefile for building and running benchmarks

CC = gcc
CFLAGS = -Wall -Wextra -O2 -std=c11
LDFLAGS = -lm

# Debug build flags
DEBUG_CFLAGS = -Wall -Wextra -g -O0 -std=c11 -DDEBUG

# Source files
SRC_DIR = src
BUILD_DIR = build
RESULTS_DIR = benchmark_results

SOURCES = $(SRC_DIR)/btree.c $(SRC_DIR)/benchmark.c
HEADERS = $(SRC_DIR)/btree.h
OBJECTS = $(BUILD_DIR)/btree.o $(BUILD_DIR)/benchmark.o
TARGET = $(BUILD_DIR)/btree_benchmark

# Test sources
TEST_SRC = tests/test_btree.c
TEST_TARGET = $(BUILD_DIR)/test_btree

.PHONY: all clean test benchmark run debug help dirs

# Default target
all: dirs $(TARGET)

# Create build directories
dirs:
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(RESULTS_DIR)

# Build the benchmark executable
$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Compile btree.c
$(BUILD_DIR)/btree.o: $(SRC_DIR)/btree.c $(HEADERS)
	$(CC) $(CFLAGS) -c -o $@ $<

# Compile benchmark.c
$(BUILD_DIR)/benchmark.o: $(SRC_DIR)/benchmark.c $(HEADERS)
	$(CC) $(CFLAGS) -c -o $@ $<

# Debug build
debug: CFLAGS = $(DEBUG_CFLAGS)
debug: clean dirs $(TARGET)

# Build and run tests
test: dirs $(TEST_TARGET)
	./$(TEST_TARGET)

$(TEST_TARGET): $(SRC_DIR)/btree.c tests/test_btree.c $(HEADERS)
	$(CC) $(CFLAGS) -o $@ $(SRC_DIR)/btree.c tests/test_btree.c $(LDFLAGS)

# Run the benchmark
benchmark: all
	@echo "Running B-tree benchmark suite..."
	@echo "Results will be saved to $(RESULTS_DIR)/benchmark_results.txt"
	./$(TARGET) | tee $(RESULTS_DIR)/benchmark_results.txt

# Alias for benchmark
run: benchmark

# Run with different configurations
benchmark-small: all
	@echo "Running small benchmark (1K-10K records)..."
	./$(TARGET) small

benchmark-large: all
	@echo "Running large benchmark (up to 10M records)..."
	./$(TARGET) large

# Generate performance report
report: benchmark
	@echo "Generating performance report..."
	python3 tests/generate_tests.py --analyze $(RESULTS_DIR)/benchmark_results.txt

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)
	rm -f $(RESULTS_DIR)/*.txt

# Deep clean including results
distclean: clean
	rm -rf $(RESULTS_DIR)

# Help target
help:
	@echo "B-Tree Indexing Performance Analysis"
	@echo ""
	@echo "Available targets:"
	@echo "  all        - Build the benchmark executable (default)"
	@echo "  benchmark  - Build and run the full benchmark suite"
	@echo "  run        - Alias for benchmark"
	@echo "  test       - Build and run unit tests"
	@echo "  debug      - Build with debug symbols"
	@echo "  clean      - Remove build artifacts"
	@echo "  distclean  - Remove build artifacts and results"
	@echo "  help       - Show this help message"
	@echo ""
	@echo "Example usage:"
	@echo "  make                    # Build the benchmark"
	@echo "  make benchmark          # Run benchmarks and save results"
	@echo "  make test               # Run unit tests"
	@echo ""
	@echo "Requirements:"
	@echo "  - GCC compiler"
	@echo "  - Python 3 (for test generation)"
	@echo "  - UNIX-like environment (Linux, macOS, WSL)"
