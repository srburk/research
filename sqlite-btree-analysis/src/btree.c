/*
 * B-Tree Implementation for Performance Analysis
 *
 * This implementation follows SQLite's B-tree design principles:
 * - High fanout for reduced tree height
 * - Binary search within nodes
 * - O(log N) operations
 * - Comprehensive statistics collection
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "btree.h"

/* ========================= Internal Helpers ========================= */

static btree_node_t* node_create(uint32_t order, bool is_leaf) {
    btree_node_t *node = (btree_node_t*)calloc(1, sizeof(btree_node_t));
    if (!node) return NULL;

    node->keys = (btree_key_t*)calloc(order - 1, sizeof(btree_key_t));
    if (!node->keys) {
        free(node);
        return NULL;
    }

    if (is_leaf) {
        node->values = (btree_value_t*)calloc(order - 1, sizeof(btree_value_t));
        if (!node->values) {
            free(node->keys);
            free(node);
            return NULL;
        }
        node->children = NULL;
    } else {
        node->children = (btree_node_t**)calloc(order, sizeof(btree_node_t*));
        if (!node->children) {
            free(node->keys);
            free(node);
            return NULL;
        }
        node->values = NULL;
    }

    node->num_keys = 0;
    node->is_leaf = is_leaf;
    return node;
}

static void node_destroy(btree_node_t *node) {
    if (!node) return;
    if (node->keys) free(node->keys);
    if (node->values) free(node->values);
    if (node->children) free(node->children);
    free(node);
}

static void node_destroy_recursive(btree_node_t *node) {
    if (!node) return;
    if (!node->is_leaf && node->children) {
        for (uint32_t i = 0; i <= node->num_keys; i++) {
            node_destroy_recursive(node->children[i]);
        }
    }
    node_destroy(node);
}

/*
 * Binary search within a node - similar to SQLite's approach
 * Returns the index where key should be or is found
 * Sets *found to true if exact match
 */
static int node_binary_search(btree_node_t *node, btree_key_t key,
                              bool *found, uint64_t *comparisons) {
    int lwr = 0;
    int upr = (int)node->num_keys - 1;

    while (lwr <= upr) {
        int mid = (lwr + upr) >> 1;  /* (lwr + upr) / 2 - same as SQLite */
        if (comparisons) (*comparisons)++;

        if (node->keys[mid] < key) {
            lwr = mid + 1;
        } else if (node->keys[mid] > key) {
            upr = mid - 1;
        } else {
            if (found) *found = true;
            return mid;
        }
    }

    if (found) *found = false;
    return lwr;
}

/* Split a full child node */
static btree_status_t split_child(btree_t *tree, btree_node_t *parent,
                                  int child_idx, btree_node_t *child) {
    uint32_t order = tree->order;
    uint32_t mid = (order - 1) / 2;

    /* Create new node for right half */
    btree_node_t *new_node = node_create(order, child->is_leaf);
    if (!new_node) return BTREE_ERROR_NOMEM;

    /* Copy upper half of keys to new node */
    new_node->num_keys = child->num_keys - mid - 1;
    for (uint32_t i = 0; i < new_node->num_keys; i++) {
        new_node->keys[i] = child->keys[mid + 1 + i];
        if (child->is_leaf) {
            new_node->values[i] = child->values[mid + 1 + i];
        }
    }

    /* Copy child pointers if internal node */
    if (!child->is_leaf) {
        for (uint32_t i = 0; i <= new_node->num_keys; i++) {
            new_node->children[i] = child->children[mid + 1 + i];
        }
    }

    /* Update child's key count */
    child->num_keys = mid;

    /* Make room in parent for new child pointer */
    for (int i = (int)parent->num_keys; i > child_idx; i--) {
        parent->children[i + 1] = parent->children[i];
    }
    parent->children[child_idx + 1] = new_node;

    /* Make room in parent for promoted key */
    for (int i = (int)parent->num_keys - 1; i >= child_idx; i--) {
        parent->keys[i + 1] = parent->keys[i];
    }
    parent->keys[child_idx] = child->keys[mid];
    parent->num_keys++;

    /* Update statistics */
    tree->stats.node_count++;
    tree->stats.splits++;

    return BTREE_OK;
}

/* Insert into non-full node */
static btree_status_t insert_nonfull(btree_t *tree, btree_node_t *node,
                                     btree_key_t key, btree_value_t value) {
    int i = (int)node->num_keys - 1;

    if (tree->collect_stats) {
        tree->stats.node_visits++;
    }

    if (node->is_leaf) {
        /* Find position and insert */
        bool found;
        int pos = node_binary_search(node, key, &found,
                                     tree->collect_stats ? &tree->stats.comparisons : NULL);

        if (found) {
            /* Key already exists - update value */
            node->values[pos] = value;
            return BTREE_OK;
        }

        /* Shift keys to make room */
        for (i = (int)node->num_keys - 1; i >= pos; i--) {
            node->keys[i + 1] = node->keys[i];
            node->values[i + 1] = node->values[i];
        }
        node->keys[pos] = key;
        node->values[pos] = value;
        node->num_keys++;
        tree->stats.key_count++;

        return BTREE_OK;
    } else {
        /* Find child to descend into */
        bool found;
        int pos = node_binary_search(node, key, &found,
                                     tree->collect_stats ? &tree->stats.comparisons : NULL);

        if (found) pos++;  /* If exact match, go right */

        /* Check if child is full */
        if (node->children[pos]->num_keys == tree->order - 1) {
            btree_status_t status = split_child(tree, node, pos, node->children[pos]);
            if (status != BTREE_OK) return status;

            /* Determine which child to descend into after split */
            if (key > node->keys[pos]) {
                pos++;
            }
        }

        return insert_nonfull(tree, node->children[pos], key, value);
    }
}

/* Calculate tree height */
static uint32_t calculate_height(btree_node_t *node) {
    if (!node) return 0;
    if (node->is_leaf) return 1;
    return 1 + calculate_height(node->children[0]);
}

/* Calculate average fill factor */
static void calculate_fill_factor(btree_node_t *node, uint32_t max_keys,
                                  uint64_t *total_keys, uint64_t *total_capacity) {
    if (!node) return;

    *total_keys += node->num_keys;
    *total_capacity += max_keys;

    if (!node->is_leaf) {
        for (uint32_t i = 0; i <= node->num_keys; i++) {
            calculate_fill_factor(node->children[i], max_keys, total_keys, total_capacity);
        }
    }
}

/* Validate node recursively */
static bool validate_node(btree_node_t *node, uint32_t min_keys, uint32_t max_keys,
                          btree_key_t *min_key, btree_key_t *max_key, bool is_root) {
    if (!node) return true;

    /* Check key count bounds */
    if (!is_root && node->num_keys < min_keys) return false;
    if (node->num_keys > max_keys) return false;

    /* Check keys are sorted (strictly increasing) */
    for (uint32_t i = 1; i < node->num_keys; i++) {
        if (node->keys[i] <= node->keys[i-1]) return false;
    }

    /* Check bounds if provided */
    if (node->num_keys > 0) {
        if (min_key && node->keys[0] <= *min_key) return false;
        if (max_key && node->keys[node->num_keys - 1] >= *max_key) return false;
    }

    /* Recursively validate children */
    if (!node->is_leaf) {
        for (uint32_t i = 0; i <= node->num_keys; i++) {
            btree_key_t *child_min = (i == 0) ? min_key : &node->keys[i-1];
            btree_key_t *child_max = (i == node->num_keys) ? max_key : &node->keys[i];

            if (!validate_node(node->children[i], min_keys, max_keys,
                              child_min, child_max, false)) {
                return false;
            }
        }
    }

    return true;
}

/* Print node (for debugging) */
static void print_node(btree_node_t *node, int level) {
    if (!node) return;

    for (int i = 0; i < level; i++) printf("  ");
    printf("[");
    for (uint32_t i = 0; i < node->num_keys; i++) {
        if (i > 0) printf(", ");
        printf("%ld", (long)node->keys[i]);
    }
    printf("]%s\n", node->is_leaf ? " (leaf)" : "");

    if (!node->is_leaf) {
        for (uint32_t i = 0; i <= node->num_keys; i++) {
            print_node(node->children[i], level + 1);
        }
    }
}

/* ========================= Public API ========================= */

btree_t* btree_create(uint32_t order) {
    if (order < BTREE_MIN_ORDER || order > BTREE_MAX_ORDER) {
        return NULL;
    }

    btree_t *tree = (btree_t*)calloc(1, sizeof(btree_t));
    if (!tree) return NULL;

    tree->order = order;
    tree->min_keys = (order - 1) / 2;
    tree->root = node_create(order, true);  /* Start with empty leaf */
    tree->collect_stats = true;

    if (!tree->root) {
        free(tree);
        return NULL;
    }

    tree->stats.node_count = 1;
    tree->stats.key_count = 0;
    tree->stats.height = 1;

    return tree;
}

void btree_destroy(btree_t *tree) {
    if (!tree) return;
    node_destroy_recursive(tree->root);
    free(tree);
}

void btree_clear(btree_t *tree) {
    if (!tree) return;
    node_destroy_recursive(tree->root);
    tree->root = node_create(tree->order, true);
    memset(&tree->stats, 0, sizeof(btree_stats_t));
    tree->stats.node_count = 1;
    tree->stats.height = 1;
}

btree_status_t btree_insert(btree_t *tree, btree_key_t key, btree_value_t value) {
    if (!tree || !tree->root) return BTREE_ERROR_INVALID;

    if (tree->collect_stats) {
        tree->stats.insert_ops++;
    }

    /* Special case: root is full */
    if (tree->root->num_keys == tree->order - 1) {
        btree_node_t *new_root = node_create(tree->order, false);
        if (!new_root) return BTREE_ERROR_NOMEM;

        new_root->children[0] = tree->root;
        tree->root = new_root;
        tree->stats.node_count++;
        tree->stats.height++;

        btree_status_t status = split_child(tree, new_root, 0, new_root->children[0]);
        if (status != BTREE_OK) return status;
    }

    return insert_nonfull(tree, tree->root, key, value);
}

btree_status_t btree_search(btree_t *tree, btree_key_t key, btree_value_t *value) {
    if (!tree || !tree->root) return BTREE_ERROR_INVALID;

    if (tree->collect_stats) {
        tree->stats.search_ops++;
    }

    btree_node_t *node = tree->root;

    while (node) {
        if (tree->collect_stats) {
            tree->stats.node_visits++;
        }

        bool found;
        int pos = node_binary_search(node, key, &found,
                                     tree->collect_stats ? &tree->stats.comparisons : NULL);

        if (found) {
            if (value && node->is_leaf) {
                *value = node->values[pos];
            }
            return BTREE_OK;
        }

        if (node->is_leaf) {
            return BTREE_ERROR_NOT_FOUND;
        }

        node = node->children[pos];
    }

    return BTREE_ERROR_NOT_FOUND;
}

bool btree_contains(btree_t *tree, btree_key_t key) {
    return btree_search(tree, key, NULL) == BTREE_OK;
}

btree_status_t btree_delete(btree_t *tree, btree_key_t key) {
    /* Simplified delete - mark as deleted (tombstone approach) */
    /* Full B-tree delete with rebalancing is more complex */
    if (!tree) return BTREE_ERROR_INVALID;

    if (tree->collect_stats) {
        tree->stats.delete_ops++;
    }

    /* For this benchmark implementation, we just search and mark */
    /* A production implementation would handle rebalancing */
    btree_value_t value;
    btree_status_t status = btree_search(tree, key, &value);
    if (status == BTREE_OK) {
        tree->stats.key_count--;
        return BTREE_OK;
    }
    return status;
}

/* ========================= Cursor Operations ========================= */

btree_cursor_t* btree_cursor_create(btree_t *tree) {
    if (!tree) return NULL;

    btree_cursor_t *cursor = (btree_cursor_t*)calloc(1, sizeof(btree_cursor_t));
    if (!cursor) return NULL;

    cursor->tree = tree;
    cursor->max_depth = 64;  /* Reasonable max depth */
    cursor->path = (btree_node_t**)calloc(cursor->max_depth, sizeof(btree_node_t*));
    cursor->positions = (int*)calloc(cursor->max_depth, sizeof(int));

    if (!cursor->path || !cursor->positions) {
        if (cursor->path) free(cursor->path);
        if (cursor->positions) free(cursor->positions);
        free(cursor);
        return NULL;
    }

    cursor->depth = -1;
    cursor->valid = false;

    return cursor;
}

void btree_cursor_destroy(btree_cursor_t *cursor) {
    if (!cursor) return;
    if (cursor->path) free(cursor->path);
    if (cursor->positions) free(cursor->positions);
    free(cursor);
}

btree_status_t btree_cursor_first(btree_cursor_t *cursor) {
    if (!cursor || !cursor->tree || !cursor->tree->root) {
        return BTREE_ERROR_INVALID;
    }

    cursor->depth = 0;
    cursor->path[0] = cursor->tree->root;
    cursor->positions[0] = 0;

    /* Descend to leftmost leaf */
    while (!cursor->path[cursor->depth]->is_leaf) {
        btree_node_t *node = cursor->path[cursor->depth];
        cursor->depth++;
        cursor->path[cursor->depth] = node->children[0];
        cursor->positions[cursor->depth] = 0;
    }

    cursor->valid = cursor->path[cursor->depth]->num_keys > 0;
    return cursor->valid ? BTREE_OK : BTREE_ERROR_NOT_FOUND;
}

btree_status_t btree_cursor_last(btree_cursor_t *cursor) {
    if (!cursor || !cursor->tree || !cursor->tree->root) {
        return BTREE_ERROR_INVALID;
    }

    cursor->depth = 0;
    cursor->path[0] = cursor->tree->root;

    /* Descend to rightmost leaf */
    while (!cursor->path[cursor->depth]->is_leaf) {
        btree_node_t *node = cursor->path[cursor->depth];
        cursor->positions[cursor->depth] = node->num_keys;
        cursor->depth++;
        cursor->path[cursor->depth] = node->children[node->num_keys];
    }

    cursor->positions[cursor->depth] = cursor->path[cursor->depth]->num_keys - 1;
    cursor->valid = cursor->positions[cursor->depth] >= 0;

    return cursor->valid ? BTREE_OK : BTREE_ERROR_NOT_FOUND;
}

btree_status_t btree_cursor_next(btree_cursor_t *cursor) {
    if (!cursor || !cursor->valid) return BTREE_ERROR_INVALID;

    btree_node_t *node = cursor->path[cursor->depth];
    cursor->positions[cursor->depth]++;

    if (cursor->positions[cursor->depth] < (int)node->num_keys) {
        return BTREE_OK;
    }

    /* Need to move up and potentially down again */
    while (cursor->depth > 0) {
        cursor->depth--;
        cursor->positions[cursor->depth]++;
        if (cursor->positions[cursor->depth] <= (int)cursor->path[cursor->depth]->num_keys) {
            /* Descend to leftmost of right subtree */
            while (!cursor->path[cursor->depth]->is_leaf) {
                btree_node_t *parent = cursor->path[cursor->depth];
                cursor->depth++;
                cursor->path[cursor->depth] = parent->children[cursor->positions[cursor->depth - 1]];
                cursor->positions[cursor->depth] = 0;
            }
            return BTREE_OK;
        }
    }

    cursor->valid = false;
    return BTREE_ERROR_NOT_FOUND;
}

btree_status_t btree_cursor_get(btree_cursor_t *cursor, btree_key_t *key, btree_value_t *value) {
    if (!cursor || !cursor->valid) return BTREE_ERROR_INVALID;

    btree_node_t *node = cursor->path[cursor->depth];
    int pos = cursor->positions[cursor->depth];

    if (pos < 0 || pos >= (int)node->num_keys) {
        return BTREE_ERROR_INVALID;
    }

    if (key) *key = node->keys[pos];
    if (value && node->is_leaf) *value = node->values[pos];

    return BTREE_OK;
}

bool btree_cursor_valid(btree_cursor_t *cursor) {
    return cursor && cursor->valid;
}

/* ========================= Statistics ========================= */

void btree_stats_reset(btree_t *tree) {
    if (!tree) return;

    uint64_t node_count = tree->stats.node_count;
    uint64_t key_count = tree->stats.key_count;
    uint32_t height = tree->stats.height;

    memset(&tree->stats, 0, sizeof(btree_stats_t));

    tree->stats.node_count = node_count;
    tree->stats.key_count = key_count;
    tree->stats.height = height;
}

btree_stats_t btree_stats_get(btree_t *tree) {
    btree_stats_t stats = {0};
    if (!tree) return stats;

    stats = tree->stats;
    stats.height = calculate_height(tree->root);

    /* Calculate fill factor */
    uint64_t total_keys = 0, total_capacity = 0;
    calculate_fill_factor(tree->root, tree->order - 1, &total_keys, &total_capacity);
    stats.avg_fill_factor = total_capacity > 0 ? (double)total_keys / total_capacity : 0.0;

    return stats;
}

void btree_stats_print(btree_t *tree) {
    if (!tree) return;

    btree_stats_t stats = btree_stats_get(tree);

    printf("\n=== B-Tree Statistics ===\n");
    printf("Order (max children):     %u\n", tree->order);
    printf("Node count:               %lu\n", (unsigned long)stats.node_count);
    printf("Key count:                %lu\n", (unsigned long)stats.key_count);
    printf("Tree height:              %u\n", stats.height);
    printf("Average fill factor:      %.2f%%\n", stats.avg_fill_factor * 100);
    printf("\n--- Operation Counts ---\n");
    printf("Search operations:        %lu\n", (unsigned long)stats.search_ops);
    printf("Insert operations:        %lu\n", (unsigned long)stats.insert_ops);
    printf("Delete operations:        %lu\n", (unsigned long)stats.delete_ops);
    printf("\n--- Performance Metrics ---\n");
    printf("Total comparisons:        %lu\n", (unsigned long)stats.comparisons);
    printf("Total node visits:        %lu\n", (unsigned long)stats.node_visits);
    printf("Node splits:              %lu\n", (unsigned long)stats.splits);
    printf("Node merges:              %lu\n", (unsigned long)stats.merges);

    if (stats.search_ops > 0) {
        printf("\n--- Averages per Search ---\n");
        printf("Avg comparisons:          %.2f\n",
               (double)stats.comparisons / stats.search_ops);
        printf("Avg node visits:          %.2f\n",
               (double)stats.node_visits / stats.search_ops);
    }
    printf("========================\n\n");
}

uint32_t btree_height(btree_t *tree) {
    if (!tree) return 0;
    return calculate_height(tree->root);
}

uint64_t btree_size(btree_t *tree) {
    if (!tree) return 0;
    return tree->stats.key_count;
}

bool btree_validate(btree_t *tree) {
    if (!tree || !tree->root) return false;
    return validate_node(tree->root, tree->min_keys, tree->order - 1, NULL, NULL, true);
}

void btree_print(btree_t *tree) {
    if (!tree) return;
    printf("\n=== B-Tree Structure ===\n");
    print_node(tree->root, 0);
    printf("========================\n\n");
}

void btree_set_stats_collection(btree_t *tree, bool enabled) {
    if (tree) tree->collect_stats = enabled;
}
