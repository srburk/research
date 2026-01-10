/*
 * B-Tree Implementation for Performance Analysis
 *
 * This implementation demonstrates B-tree concepts used in SQLite indexing.
 * Designed for educational purposes and benchmarking.
 *
 * Key features:
 * - Configurable order (fanout)
 * - O(log N) search, insert, delete
 * - Performance metrics collection
 */

#ifndef BTREE_H
#define BTREE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* Configuration constants */
#define BTREE_DEFAULT_ORDER 128    /* Similar to SQLite's high fanout */
#define BTREE_MIN_ORDER 3          /* Minimum order for a valid B-tree */
#define BTREE_MAX_ORDER 1024       /* Maximum supported order */

/* Error codes */
typedef enum {
    BTREE_OK = 0,
    BTREE_ERROR_NOMEM = -1,
    BTREE_ERROR_NOT_FOUND = -2,
    BTREE_ERROR_DUPLICATE = -3,
    BTREE_ERROR_INVALID = -4,
    BTREE_ERROR_CORRUPT = -5
} btree_status_t;

/* Key and value types */
typedef int64_t btree_key_t;
typedef void* btree_value_t;

/* Forward declarations */
typedef struct btree_node btree_node_t;
typedef struct btree btree_t;
typedef struct btree_cursor btree_cursor_t;
typedef struct btree_stats btree_stats_t;

/* Performance statistics */
struct btree_stats {
    uint64_t node_count;          /* Total number of nodes */
    uint64_t key_count;           /* Total number of keys */
    uint32_t height;              /* Current tree height */
    uint64_t comparisons;         /* Key comparisons performed */
    uint64_t node_visits;         /* Node visits (simulates page reads) */
    uint64_t splits;              /* Node splits performed */
    uint64_t merges;              /* Node merges performed */
    uint64_t search_ops;          /* Total search operations */
    uint64_t insert_ops;          /* Total insert operations */
    uint64_t delete_ops;          /* Total delete operations */
    double avg_fill_factor;       /* Average node fill factor (0.0 - 1.0) */
};

/* B-tree node structure */
struct btree_node {
    btree_key_t *keys;            /* Array of keys */
    btree_value_t *values;        /* Array of values (leaf nodes only) */
    btree_node_t **children;      /* Child pointers (internal nodes only) */
    uint32_t num_keys;            /* Current number of keys */
    bool is_leaf;                 /* True if this is a leaf node */
};

/* B-tree structure */
struct btree {
    btree_node_t *root;           /* Root node */
    uint32_t order;               /* Maximum keys per node = order - 1 */
    uint32_t min_keys;            /* Minimum keys per non-root node */
    btree_stats_t stats;          /* Performance statistics */
    bool collect_stats;           /* Whether to collect detailed stats */
};

/* Cursor for tree traversal */
struct btree_cursor {
    btree_t *tree;                /* The tree being traversed */
    btree_node_t **path;          /* Stack of nodes from root to current */
    int *positions;               /* Position within each node */
    int depth;                    /* Current depth in the path */
    int max_depth;                /* Maximum depth allocated */
    bool valid;                   /* Is cursor pointing to valid entry */
};

/* =========================== API Functions =========================== */

/* Tree lifecycle */
btree_t* btree_create(uint32_t order);
void btree_destroy(btree_t *tree);
void btree_clear(btree_t *tree);

/* Core operations */
btree_status_t btree_insert(btree_t *tree, btree_key_t key, btree_value_t value);
btree_status_t btree_search(btree_t *tree, btree_key_t key, btree_value_t *value);
btree_status_t btree_delete(btree_t *tree, btree_key_t key);
bool btree_contains(btree_t *tree, btree_key_t key);

/* Cursor operations */
btree_cursor_t* btree_cursor_create(btree_t *tree);
void btree_cursor_destroy(btree_cursor_t *cursor);
btree_status_t btree_cursor_first(btree_cursor_t *cursor);
btree_status_t btree_cursor_last(btree_cursor_t *cursor);
btree_status_t btree_cursor_next(btree_cursor_t *cursor);
btree_status_t btree_cursor_prev(btree_cursor_t *cursor);
btree_status_t btree_cursor_seek(btree_cursor_t *cursor, btree_key_t key);
btree_status_t btree_cursor_get(btree_cursor_t *cursor, btree_key_t *key, btree_value_t *value);
bool btree_cursor_valid(btree_cursor_t *cursor);

/* Statistics and diagnostics */
void btree_stats_reset(btree_t *tree);
btree_stats_t btree_stats_get(btree_t *tree);
void btree_stats_print(btree_t *tree);
uint32_t btree_height(btree_t *tree);
uint64_t btree_size(btree_t *tree);

/* Validation */
bool btree_validate(btree_t *tree);
void btree_print(btree_t *tree);

/* Configuration */
void btree_set_stats_collection(btree_t *tree, bool enabled);

#endif /* BTREE_H */
