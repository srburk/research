/*
 * B-Tree Performance Benchmark Suite
 *
 * This benchmark demonstrates how B-trees accelerate indexing operations
 * compared to linear search, with detailed performance metrics.
 *
 * Metrics collected:
 * - Insertion throughput (ops/sec)
 * - Search throughput (ops/sec)
 * - Average comparisons per operation
 * - Average node visits (simulated page reads)
 * - Tree height vs data size
 * - Fill factor analysis
 */

/* Enable POSIX features for clock_gettime */
#define _POSIX_C_SOURCE 199309L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <math.h>
#include "btree.h"

/* ========================= Timing Utilities ========================= */

typedef struct {
    struct timespec start;
    struct timespec end;
} bench_timer_t;

static void timer_start(bench_timer_t *t) {
    clock_gettime(CLOCK_MONOTONIC, &t->start);
}

static void timer_stop(bench_timer_t *t) {
    clock_gettime(CLOCK_MONOTONIC, &t->end);
}

static double timer_elapsed_ms(bench_timer_t *t) {
    double start_ms = t->start.tv_sec * 1000.0 + t->start.tv_nsec / 1000000.0;
    double end_ms = t->end.tv_sec * 1000.0 + t->end.tv_nsec / 1000000.0;
    return end_ms - start_ms;
}

/* ========================= Test Data Generation ========================= */

typedef struct {
    int64_t *keys;
    size_t count;
} test_data_t;

static test_data_t* generate_sequential_data(size_t count) {
    test_data_t *data = malloc(sizeof(test_data_t));
    data->keys = malloc(count * sizeof(int64_t));
    data->count = count;

    for (size_t i = 0; i < count; i++) {
        data->keys[i] = (int64_t)(i + 1);
    }
    return data;
}

static test_data_t* generate_random_data(size_t count, unsigned int seed) {
    test_data_t *data = malloc(sizeof(test_data_t));
    data->keys = malloc(count * sizeof(int64_t));
    data->count = count;

    srand(seed);
    for (size_t i = 0; i < count; i++) {
        /* Generate unique random keys using Fisher-Yates-like approach */
        data->keys[i] = (int64_t)rand() * (int64_t)rand() + (int64_t)i;
    }
    return data;
}

static void shuffle_data(test_data_t *data, unsigned int seed) {
    srand(seed);
    for (size_t i = data->count - 1; i > 0; i--) {
        size_t j = rand() % (i + 1);
        int64_t temp = data->keys[i];
        data->keys[i] = data->keys[j];
        data->keys[j] = temp;
    }
}

static void free_test_data(test_data_t *data) {
    if (data) {
        free(data->keys);
        free(data);
    }
}

/* ========================= Benchmark Results ========================= */

typedef struct {
    const char *name;
    size_t data_size;
    uint32_t tree_order;
    double insert_time_ms;
    double search_time_ms;
    double insert_ops_per_sec;
    double search_ops_per_sec;
    uint32_t tree_height;
    double avg_comparisons_per_search;
    double avg_node_visits_per_search;
    double fill_factor;
    uint64_t total_nodes;
} benchmark_result_t;

static void print_result(benchmark_result_t *result) {
    printf("%-30s | %10zu | %5u | %10.2f | %12.0f | %12.0f | %6u | %8.2f | %8.2f | %6.1f%%\n",
           result->name,
           result->data_size,
           result->tree_order,
           result->insert_time_ms,
           result->insert_ops_per_sec,
           result->search_ops_per_sec,
           result->tree_height,
           result->avg_comparisons_per_search,
           result->avg_node_visits_per_search,
           result->fill_factor * 100);
}

static void print_header(void) {
    printf("\n");
    printf("%-30s | %10s | %5s | %10s | %12s | %12s | %6s | %8s | %8s | %7s\n",
           "Benchmark", "Records", "Order", "Insert(ms)", "Insert/sec", "Search/sec",
           "Height", "Avg Cmp", "Avg Node", "Fill%");
    printf("%-30s-+-%10s-+-%5s-+-%10s-+-%12s-+-%12s-+-%6s-+-%8s-+-%8s-+-%7s\n",
           "------------------------------", "----------", "-----", "----------",
           "------------", "------------", "------", "--------", "--------", "-------");
}

/* ========================= Linear Search Baseline ========================= */

typedef struct {
    int64_t *keys;
    void **values;
    size_t count;
    size_t capacity;
} linear_array_t;

static linear_array_t* linear_create(size_t capacity) {
    linear_array_t *arr = malloc(sizeof(linear_array_t));
    arr->keys = malloc(capacity * sizeof(int64_t));
    arr->values = malloc(capacity * sizeof(void*));
    arr->count = 0;
    arr->capacity = capacity;
    return arr;
}

static void linear_insert(linear_array_t *arr, int64_t key, void *value) {
    if (arr->count < arr->capacity) {
        arr->keys[arr->count] = key;
        arr->values[arr->count] = value;
        arr->count++;
    }
}

static int linear_search(linear_array_t *arr, int64_t key, uint64_t *comparisons) {
    for (size_t i = 0; i < arr->count; i++) {
        (*comparisons)++;
        if (arr->keys[i] == key) return 1;
    }
    return 0;
}

static void linear_destroy(linear_array_t *arr) {
    if (arr) {
        free(arr->keys);
        free(arr->values);
        free(arr);
    }
}

/* ========================= Benchmark Functions ========================= */

static benchmark_result_t run_btree_benchmark(const char *name, test_data_t *data,
                                               uint32_t order, int search_count) {
    benchmark_result_t result = {0};
    result.name = name;
    result.data_size = data->count;
    result.tree_order = order;

    btree_t *tree = btree_create(order);
    if (!tree) {
        fprintf(stderr, "Failed to create B-tree\n");
        return result;
    }

    bench_timer_t timer;

    /* Benchmark insertions */
    timer_start(&timer);
    for (size_t i = 0; i < data->count; i++) {
        btree_insert(tree, data->keys[i], (void*)(intptr_t)data->keys[i]);
    }
    timer_stop(&timer);
    result.insert_time_ms = timer_elapsed_ms(&timer);
    result.insert_ops_per_sec = (data->count / result.insert_time_ms) * 1000.0;

    /* Get tree stats after insertions */
    btree_stats_t stats = btree_stats_get(tree);
    result.tree_height = stats.height;
    result.fill_factor = stats.avg_fill_factor;
    result.total_nodes = stats.node_count;

    /* Reset stats for search benchmark */
    btree_stats_reset(tree);

    /* Benchmark searches */
    timer_start(&timer);
    for (int i = 0; i < search_count; i++) {
        size_t idx = rand() % data->count;
        btree_search(tree, data->keys[idx], NULL);
    }
    timer_stop(&timer);
    result.search_time_ms = timer_elapsed_ms(&timer);
    result.search_ops_per_sec = (search_count / result.search_time_ms) * 1000.0;

    /* Get search statistics */
    stats = btree_stats_get(tree);
    result.avg_comparisons_per_search = (double)stats.comparisons / search_count;
    result.avg_node_visits_per_search = (double)stats.node_visits / search_count;

    btree_destroy(tree);
    return result;
}

static benchmark_result_t run_linear_benchmark(const char *name, test_data_t *data,
                                                int search_count) {
    benchmark_result_t result = {0};
    result.name = name;
    result.data_size = data->count;
    result.tree_order = 0;  /* N/A for linear */
    result.tree_height = 1; /* N/A for linear */
    result.fill_factor = 1.0;

    linear_array_t *arr = linear_create(data->count);
    if (!arr) return result;

    bench_timer_t timer;

    /* Benchmark insertions */
    timer_start(&timer);
    for (size_t i = 0; i < data->count; i++) {
        linear_insert(arr, data->keys[i], (void*)(intptr_t)data->keys[i]);
    }
    timer_stop(&timer);
    result.insert_time_ms = timer_elapsed_ms(&timer);
    result.insert_ops_per_sec = (data->count / result.insert_time_ms) * 1000.0;

    /* Benchmark searches */
    uint64_t total_comparisons = 0;
    timer_start(&timer);
    for (int i = 0; i < search_count; i++) {
        size_t idx = rand() % data->count;
        linear_search(arr, data->keys[idx], &total_comparisons);
    }
    timer_stop(&timer);
    result.search_time_ms = timer_elapsed_ms(&timer);
    result.search_ops_per_sec = (search_count / result.search_time_ms) * 1000.0;
    result.avg_comparisons_per_search = (double)total_comparisons / search_count;
    result.avg_node_visits_per_search = result.avg_comparisons_per_search; /* Same for linear */

    linear_destroy(arr);
    return result;
}

/* ========================= Benchmark Suites ========================= */

static void run_scaling_benchmark(void) {
    printf("\n========================================\n");
    printf("BENCHMARK 1: Scaling Analysis\n");
    printf("Shows how B-tree performance scales with data size\n");
    printf("========================================\n");

    size_t sizes[] = {1000, 10000, 100000, 500000, 1000000};
    int num_sizes = sizeof(sizes) / sizeof(sizes[0]);
    int search_count = 10000;
    uint32_t order = 128;

    print_header();

    for (int i = 0; i < num_sizes; i++) {
        test_data_t *data = generate_random_data(sizes[i], 42);

        char name[64];
        snprintf(name, sizeof(name), "B-tree (n=%zu)", sizes[i]);
        benchmark_result_t result = run_btree_benchmark(name, data, order, search_count);
        print_result(&result);

        free_test_data(data);
    }
}

static void run_order_comparison_benchmark(void) {
    printf("\n========================================\n");
    printf("BENCHMARK 2: B-tree Order Comparison\n");
    printf("Shows how different orders (fanouts) affect performance\n");
    printf("========================================\n");

    size_t data_size = 100000;
    int search_count = 10000;
    uint32_t orders[] = {4, 8, 16, 32, 64, 128, 256, 512};
    int num_orders = sizeof(orders) / sizeof(orders[0]);

    test_data_t *data = generate_random_data(data_size, 42);

    print_header();

    for (int i = 0; i < num_orders; i++) {
        char name[64];
        snprintf(name, sizeof(name), "Order=%u", orders[i]);
        benchmark_result_t result = run_btree_benchmark(name, data, orders[i], search_count);
        print_result(&result);
    }

    free_test_data(data);
}

static void run_btree_vs_linear_benchmark(void) {
    printf("\n========================================\n");
    printf("BENCHMARK 3: B-tree vs Linear Search\n");
    printf("Demonstrates the O(log N) vs O(N) difference\n");
    printf("========================================\n");

    size_t sizes[] = {100, 1000, 5000, 10000, 50000};
    int num_sizes = sizeof(sizes) / sizeof(sizes[0]);
    int search_count = 1000;

    print_header();

    for (int i = 0; i < num_sizes; i++) {
        test_data_t *data = generate_random_data(sizes[i], 42);

        /* B-tree benchmark */
        char btree_name[64];
        snprintf(btree_name, sizeof(btree_name), "B-tree (n=%zu)", sizes[i]);
        benchmark_result_t btree_result = run_btree_benchmark(btree_name, data, 128, search_count);
        print_result(&btree_result);

        /* Linear search benchmark */
        char linear_name[64];
        snprintf(linear_name, sizeof(linear_name), "Linear (n=%zu)", sizes[i]);
        benchmark_result_t linear_result = run_linear_benchmark(linear_name, data, search_count);
        print_result(&linear_result);

        /* Print speedup */
        printf("  --> B-tree speedup: %.1fx faster search, %.1fx fewer comparisons\n\n",
               linear_result.search_time_ms / btree_result.search_time_ms,
               linear_result.avg_comparisons_per_search / btree_result.avg_comparisons_per_search);

        free_test_data(data);
    }
}

static void run_insertion_pattern_benchmark(void) {
    printf("\n========================================\n");
    printf("BENCHMARK 4: Insertion Pattern Analysis\n");
    printf("Shows how insertion order affects performance\n");
    printf("========================================\n");

    size_t data_size = 100000;
    int search_count = 10000;
    uint32_t order = 128;

    print_header();

    /* Sequential insertion */
    test_data_t *seq_data = generate_sequential_data(data_size);
    benchmark_result_t seq_result = run_btree_benchmark("Sequential Insert", seq_data, order, search_count);
    print_result(&seq_result);
    free_test_data(seq_data);

    /* Random insertion */
    test_data_t *rand_data = generate_random_data(data_size, 42);
    benchmark_result_t rand_result = run_btree_benchmark("Random Insert", rand_data, order, search_count);
    print_result(&rand_result);
    free_test_data(rand_data);

    /* Shuffled sequential (pre-generated then shuffled) */
    test_data_t *shuf_data = generate_sequential_data(data_size);
    shuffle_data(shuf_data, 42);
    benchmark_result_t shuf_result = run_btree_benchmark("Shuffled Sequential", shuf_data, order, search_count);
    print_result(&shuf_result);
    free_test_data(shuf_data);
}

static void run_theoretical_analysis(void) {
    printf("\n========================================\n");
    printf("BENCHMARK 5: Theoretical vs Actual Comparison\n");
    printf("Validates O(log N) complexity\n");
    printf("========================================\n");

    size_t sizes[] = {1000, 10000, 100000, 1000000};
    int num_sizes = sizeof(sizes) / sizeof(sizes[0]);
    uint32_t order = 128;
    int search_count = 10000;

    printf("\n%-12s | %12s | %12s | %12s | %12s\n",
           "Records", "Tree Height", "log_order(N)", "Avg Cmp", "Expected Cmp");
    printf("%-12s-+-%12s-+-%12s-+-%12s-+-%12s\n",
           "------------", "------------", "------------", "------------", "------------");

    for (int i = 0; i < num_sizes; i++) {
        test_data_t *data = generate_random_data(sizes[i], 42);
        benchmark_result_t result = run_btree_benchmark("test", data, order, search_count);

        /* Calculate theoretical values */
        double log_base_order = log((double)sizes[i]) / log((double)order);
        /* Expected comparisons: height * log2(keys_per_node) */
        double expected_cmp = result.tree_height * log2((double)(order - 1));

        printf("%12zu | %12u | %12.2f | %12.2f | %12.2f\n",
               sizes[i],
               result.tree_height,
               log_base_order,
               result.avg_comparisons_per_search,
               expected_cmp);

        free_test_data(data);
    }

    printf("\nNote: Actual comparisons include binary search within each node.\n");
    printf("Total comparisons ≈ height × log2(keys_per_node)\n");
}

/* ========================= Main Entry Point ========================= */

int main(void) {
    printf("╔══════════════════════════════════════════════════════════════════╗\n");
    printf("║         B-TREE INDEXING PERFORMANCE BENCHMARK SUITE              ║\n");
    printf("║                                                                  ║\n");
    printf("║  Demonstrating how B-trees accelerate database indexing          ║\n");
    printf("║  Based on SQLite's B-tree implementation principles              ║\n");
    printf("╚══════════════════════════════════════════════════════════════════╝\n");

    /* Seed random number generator */
    srand(time(NULL));

    /* Run all benchmarks */
    run_scaling_benchmark();
    run_order_comparison_benchmark();
    run_btree_vs_linear_benchmark();
    run_insertion_pattern_benchmark();
    run_theoretical_analysis();

    printf("\n========================================\n");
    printf("BENCHMARK COMPLETE\n");
    printf("========================================\n");

    printf("\nKey Takeaways:\n");
    printf("1. B-tree search is O(log N) - search time barely increases with data size\n");
    printf("2. Higher order (fanout) reduces tree height but increases per-node search time\n");
    printf("3. B-trees are dramatically faster than linear search for large datasets\n");
    printf("4. Insertion pattern affects fill factor and tree balance\n");
    printf("5. SQLite uses order ~128 for good balance of height and node search time\n");

    return 0;
}
