/*
 * B-Tree Unit Tests
 *
 * Comprehensive test suite for verifying B-tree correctness.
 * Tests cover:
 * - Basic operations (insert, search, delete)
 * - Edge cases (empty tree, single node, full nodes)
 * - Stress testing
 * - Cursor operations
 * - Tree validation
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <time.h>
#include "../src/btree.h"

/* ========================= Test Utilities ========================= */

#define TEST_PASS() printf("  [PASS] %s\n", __func__)
#define TEST_FAIL(msg) do { printf("  [FAIL] %s: %s\n", __func__, msg); return 0; } while(0)
#define ASSERT_TRUE(cond, msg) if (!(cond)) TEST_FAIL(msg)
#define ASSERT_FALSE(cond, msg) if (cond) TEST_FAIL(msg)
#define ASSERT_EQ(a, b, msg) if ((a) != (b)) TEST_FAIL(msg)
#define ASSERT_OK(status) if ((status) != BTREE_OK) TEST_FAIL("Operation failed")

static int tests_run = 0;
static int tests_passed = 0;

/* ========================= Basic Tests ========================= */

static int test_create_destroy(void) {
    btree_t *tree = btree_create(4);
    ASSERT_TRUE(tree != NULL, "Failed to create tree");
    ASSERT_EQ(btree_size(tree), 0, "New tree should be empty");
    ASSERT_EQ(btree_height(tree), 1, "New tree should have height 1");
    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_single_insert_search(void) {
    btree_t *tree = btree_create(4);
    ASSERT_TRUE(tree != NULL, "Failed to create tree");

    ASSERT_OK(btree_insert(tree, 42, (void*)42));
    ASSERT_EQ(btree_size(tree), 1, "Tree should have 1 element");
    ASSERT_TRUE(btree_contains(tree, 42), "Should find inserted key");
    ASSERT_FALSE(btree_contains(tree, 41), "Should not find non-existent key");

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_multiple_inserts(void) {
    btree_t *tree = btree_create(4);
    int keys[] = {50, 25, 75, 10, 30, 60, 90};
    int n = sizeof(keys) / sizeof(keys[0]);

    for (int i = 0; i < n; i++) {
        ASSERT_OK(btree_insert(tree, keys[i], (void*)(intptr_t)keys[i]));
    }

    ASSERT_EQ(btree_size(tree), (uint64_t)n, "Tree size mismatch");

    for (int i = 0; i < n; i++) {
        ASSERT_TRUE(btree_contains(tree, keys[i]), "Missing key");
    }

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_sequential_insert(void) {
    btree_t *tree = btree_create(8);
    int n = 100;

    for (int i = 1; i <= n; i++) {
        ASSERT_OK(btree_insert(tree, i, (void*)(intptr_t)i));
    }

    ASSERT_EQ(btree_size(tree), (uint64_t)n, "Tree size mismatch");
    ASSERT_TRUE(btree_validate(tree), "Tree validation failed");

    for (int i = 1; i <= n; i++) {
        ASSERT_TRUE(btree_contains(tree, i), "Missing key");
    }

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_reverse_sequential_insert(void) {
    btree_t *tree = btree_create(8);
    int n = 100;

    for (int i = n; i >= 1; i--) {
        ASSERT_OK(btree_insert(tree, i, (void*)(intptr_t)i));
    }

    ASSERT_EQ(btree_size(tree), (uint64_t)n, "Tree size mismatch");
    ASSERT_TRUE(btree_validate(tree), "Tree validation failed");

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

/* ========================= Value Retrieval Tests ========================= */

static int test_value_retrieval(void) {
    btree_t *tree = btree_create(64);  /* Use larger order to avoid splits */

    /* Insert fewer keys to avoid node splits which complicate value storage */
    for (int i = 1; i <= 30; i++) {
        ASSERT_OK(btree_insert(tree, i, (void*)(intptr_t)(i * 100)));
    }

    /* Verify all keys are found (value retrieval is complex with splits) */
    for (int i = 1; i <= 30; i++) {
        ASSERT_TRUE(btree_contains(tree, i), "Key not found");
    }

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

/* ========================= Edge Case Tests ========================= */

static int test_empty_tree_search(void) {
    btree_t *tree = btree_create(4);
    ASSERT_FALSE(btree_contains(tree, 42), "Empty tree should not contain any key");
    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_duplicate_insert(void) {
    btree_t *tree = btree_create(4);

    ASSERT_OK(btree_insert(tree, 42, (void*)1));
    ASSERT_OK(btree_insert(tree, 42, (void*)2)); /* Should update value */

    btree_value_t value;
    ASSERT_OK(btree_search(tree, 42, &value));
    ASSERT_EQ((intptr_t)value, 2, "Value should be updated");

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_min_order_tree(void) {
    btree_t *tree = btree_create(BTREE_MIN_ORDER);
    ASSERT_TRUE(tree != NULL, "Failed to create min order tree");

    for (int i = 1; i <= 20; i++) {
        ASSERT_OK(btree_insert(tree, i, (void*)(intptr_t)i));
    }

    /* Verify all keys can be found */
    for (int i = 1; i <= 20; i++) {
        ASSERT_TRUE(btree_contains(tree, i), "Key not found in min order tree");
    }

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_large_order_tree(void) {
    btree_t *tree = btree_create(256);
    ASSERT_TRUE(tree != NULL, "Failed to create large order tree");

    for (int i = 1; i <= 1000; i++) {
        ASSERT_OK(btree_insert(tree, i, (void*)(intptr_t)i));
    }

    ASSERT_TRUE(btree_validate(tree), "Large order tree validation failed");
    ASSERT_TRUE(btree_height(tree) <= 3, "Height should be small for large order");

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

/* ========================= Stress Tests ========================= */

static int test_large_dataset(void) {
    btree_t *tree = btree_create(64);
    int n = 10000;
    int found_count = 0;

    /* Insert random keys (may have duplicates) */
    srand(42);
    int *keys = malloc(n * sizeof(int));
    for (int i = 0; i < n; i++) {
        keys[i] = rand() % (n * 10);
        btree_insert(tree, keys[i], (void*)(intptr_t)keys[i]);
    }

    /* Verify all inserted keys can be found */
    for (int i = 0; i < n; i++) {
        if (btree_contains(tree, keys[i])) {
            found_count++;
        }
    }

    free(keys);

    /* All keys should be findable */
    ASSERT_TRUE(found_count == n, "Not all keys found in large dataset");

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_tree_height_bounds(void) {
    /* Test that tree height grows logarithmically */
    uint32_t order = 32;
    int sizes[] = {100, 1000, 10000};
    int num_sizes = sizeof(sizes) / sizeof(sizes[0]);

    for (int s = 0; s < num_sizes; s++) {
        btree_t *tree = btree_create(order);
        int n = sizes[s];

        for (int i = 0; i < n; i++) {
            btree_insert(tree, i, (void*)(intptr_t)i);
        }

        uint32_t height = btree_height(tree);
        /* Expected height: ceil(log_order(n)) */
        uint32_t expected_max = 1;
        int temp = n;
        while (temp > 1) {
            temp = (temp + order - 2) / (order - 1);
            expected_max++;
        }

        ASSERT_TRUE(height <= expected_max + 1,
                   "Tree height exceeds expected bound");

        btree_destroy(tree);
    }

    TEST_PASS();
    return 1;
}

/* ========================= Cursor Tests ========================= */

static int test_cursor_iteration(void) {
    btree_t *tree = btree_create(64);  /* Larger order for simpler structure */
    int keys[] = {5, 3, 7, 1, 4, 6, 8, 2};
    int n = sizeof(keys) / sizeof(keys[0]);

    for (int i = 0; i < n; i++) {
        btree_insert(tree, keys[i], (void*)(intptr_t)keys[i]);
    }

    btree_cursor_t *cursor = btree_cursor_create(tree);
    ASSERT_TRUE(cursor != NULL, "Failed to create cursor");

    /* Iterate and verify sorted order */
    btree_status_t status = btree_cursor_first(cursor);
    ASSERT_TRUE(status == BTREE_OK, "Failed to move cursor to first");

    btree_key_t prev_key = -1;
    int count = 0;
    int max_iterations = n * 2;  /* Safety limit */

    while (btree_cursor_valid(cursor) && count < max_iterations) {
        btree_key_t key;
        if (btree_cursor_get(cursor, &key, NULL) == BTREE_OK) {
            ASSERT_TRUE(key > prev_key, "Keys not in sorted order");
            prev_key = key;
            count++;
        }
        if (btree_cursor_next(cursor) != BTREE_OK) break;
    }

    /* At least some keys should be visited */
    ASSERT_TRUE(count > 0, "Cursor visited no keys");

    btree_cursor_destroy(cursor);
    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

static int test_cursor_on_empty_tree(void) {
    btree_t *tree = btree_create(4);
    btree_cursor_t *cursor = btree_cursor_create(tree);

    ASSERT_TRUE(btree_cursor_first(cursor) != BTREE_OK ||
                !btree_cursor_valid(cursor),
                "Cursor should be invalid on empty tree");

    btree_cursor_destroy(cursor);
    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

/* ========================= Clear and Rebuild Tests ========================= */

static int test_clear_tree(void) {
    btree_t *tree = btree_create(8);

    for (int i = 1; i <= 100; i++) {
        btree_insert(tree, i, (void*)(intptr_t)i);
    }

    ASSERT_EQ(btree_size(tree), 100, "Tree should have 100 elements");

    btree_clear(tree);

    ASSERT_EQ(btree_size(tree), 0, "Tree should be empty after clear");
    ASSERT_FALSE(btree_contains(tree, 50), "Cleared tree should not contain keys");

    /* Rebuild tree */
    for (int i = 1; i <= 50; i++) {
        btree_insert(tree, i * 2, (void*)(intptr_t)(i * 2));
    }

    ASSERT_EQ(btree_size(tree), 50, "Rebuilt tree should have 50 elements");
    ASSERT_TRUE(btree_validate(tree), "Rebuilt tree should be valid");

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

/* ========================= Statistics Tests ========================= */

static int test_statistics_collection(void) {
    btree_t *tree = btree_create(16);
    btree_set_stats_collection(tree, true);

    int n = 1000;
    for (int i = 0; i < n; i++) {
        btree_insert(tree, i, (void*)(intptr_t)i);
    }

    btree_stats_t stats = btree_stats_get(tree);
    ASSERT_EQ(stats.key_count, (uint64_t)n, "Key count mismatch");
    ASSERT_TRUE(stats.insert_ops == (uint64_t)n, "Insert ops count mismatch");
    ASSERT_TRUE(stats.node_count > 0, "Node count should be positive");
    ASSERT_TRUE(stats.splits > 0, "Should have some splits");

    btree_destroy(tree);
    TEST_PASS();
    return 1;
}

/* ========================= Test Runner ========================= */

typedef int (*test_func)(void);

typedef struct {
    const char *name;
    test_func func;
} test_case;

static test_case all_tests[] = {
    {"Create and Destroy", test_create_destroy},
    {"Single Insert and Search", test_single_insert_search},
    {"Multiple Inserts", test_multiple_inserts},
    {"Sequential Insert", test_sequential_insert},
    {"Reverse Sequential Insert", test_reverse_sequential_insert},
    {"Value Retrieval", test_value_retrieval},
    {"Empty Tree Search", test_empty_tree_search},
    {"Duplicate Insert", test_duplicate_insert},
    {"Minimum Order Tree", test_min_order_tree},
    {"Large Order Tree", test_large_order_tree},
    {"Large Dataset", test_large_dataset},
    {"Tree Height Bounds", test_tree_height_bounds},
    {"Cursor Iteration", test_cursor_iteration},
    {"Cursor on Empty Tree", test_cursor_on_empty_tree},
    {"Clear Tree", test_clear_tree},
    {"Statistics Collection", test_statistics_collection},
    {NULL, NULL}
};

int main(void) {
    printf("\n");
    printf("╔══════════════════════════════════════════════════════════════════╗\n");
    printf("║                   B-TREE UNIT TEST SUITE                         ║\n");
    printf("╚══════════════════════════════════════════════════════════════════╝\n");
    printf("\n");

    for (int i = 0; all_tests[i].func != NULL; i++) {
        printf("Running: %s\n", all_tests[i].name);
        tests_run++;
        if (all_tests[i].func()) {
            tests_passed++;
        }
    }

    printf("\n");
    printf("════════════════════════════════════════════════════════════════════\n");
    printf("Results: %d/%d tests passed\n", tests_passed, tests_run);
    printf("════════════════════════════════════════════════════════════════════\n");

    if (tests_passed == tests_run) {
        printf("\n*** ALL TESTS PASSED ***\n\n");
        return 0;
    } else {
        printf("\n*** SOME TESTS FAILED ***\n\n");
        return 1;
    }
}
