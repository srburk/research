#!/usr/bin/env python3
"""
B-Tree Benchmark Visualization

Generates charts showing:
1. B-tree vs Linear search comparison (comparisons)
2. Scaling analysis (height and comparisons vs data size)
3. Order comparison
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Create output directory
os.makedirs('assets', exist_ok=True)

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 11

# Data from benchmark results
# B-tree vs Linear comparison data
btree_linear_data = {
    'sizes': [100, 1000, 5000, 10000, 50000],
    'btree_comparisons': [5.83, 9.16, 11.39, 12.34, 14.74],
    'linear_comparisons': [49.98, 516.11, 2517.09, 5113.22, 24596.05],
    'btree_search_ops': [20772746, 14225965, 11889758, 10716161, 7264433],
    'linear_search_ops': [24796667, 5384885, 1256949, 636567, 133078],
}

# Scaling data
scaling_data = {
    'sizes': [1000, 10000, 100000, 500000, 1000000],
    'heights': [2, 2, 3, 3, 4],
    'comparisons': [9.21, 12.40, 15.75, 18.06, 19.11],
    'search_ops': [14985000, 10701803, 6829239, 3937456, 3287894],
}

# Order comparison data
order_data = {
    'orders': [4, 8, 16, 32, 64, 128, 256, 512],
    'heights': [13, 7, 5, 4, 3, 3, 3, 2],
    'comparisons': [16.42, 16.14, 15.87, 15.89, 15.79, 15.73, 15.74, 15.69],
    'search_ops': [3300839, 3972537, 4956035, 5705004, 5983413, 6759625, 6941779, 6936949],
}

# Create figure with subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# ============== Plot 1: B-tree vs Linear Comparisons ==============
ax1 = axes[0, 0]
x = np.arange(len(btree_linear_data['sizes']))
width = 0.35

bars1 = ax1.bar(x - width/2, btree_linear_data['btree_comparisons'], width,
                label='B-tree', color='#2ecc71', edgecolor='black', linewidth=0.5)
bars2 = ax1.bar(x + width/2, btree_linear_data['linear_comparisons'], width,
                label='Linear', color='#e74c3c', edgecolor='black', linewidth=0.5)

ax1.set_xlabel('Dataset Size')
ax1.set_ylabel('Average Comparisons per Search')
ax1.set_title('B-tree vs Linear Search: Comparisons\n(Lower is Better)', fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels([f'{s:,}' for s in btree_linear_data['sizes']])
ax1.legend()
ax1.set_yscale('log')

# Add value labels on bars
for bar in bars1:
    height = bar.get_height()
    ax1.annotate(f'{height:.1f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=8)

for bar in bars2:
    height = bar.get_height()
    ax1.annotate(f'{height:.0f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=8)

# ============== Plot 2: Scaling Analysis ==============
ax2 = axes[0, 1]
ax2_twin = ax2.twinx()

line1 = ax2.plot(scaling_data['sizes'], scaling_data['comparisons'],
                 'o-', color='#3498db', linewidth=2, markersize=8, label='Avg Comparisons')
line2 = ax2_twin.plot(scaling_data['sizes'], scaling_data['heights'],
                      's--', color='#9b59b6', linewidth=2, markersize=8, label='Tree Height')

ax2.set_xlabel('Number of Records')
ax2.set_ylabel('Average Comparisons per Search', color='#3498db')
ax2_twin.set_ylabel('Tree Height', color='#9b59b6')
ax2.set_title('B-tree Scaling: O(log N) Complexity\n(Comparisons grow logarithmically)', fontweight='bold')
ax2.set_xscale('log')
ax2.tick_params(axis='y', labelcolor='#3498db')
ax2_twin.tick_params(axis='y', labelcolor='#9b59b6')

# Combined legend
lines1, labels1 = ax2.get_legend_handles_labels()
lines2, labels2 = ax2_twin.get_legend_handles_labels()
ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

# Add theoretical O(log N) reference line
theoretical_comps = [7 * np.log2(s) / np.log2(128) for s in scaling_data['sizes']]
ax2.plot(scaling_data['sizes'], theoretical_comps, ':', color='gray',
         linewidth=1.5, alpha=0.7, label='O(log N) reference')

# ============== Plot 3: Order (Fanout) Comparison ==============
ax3 = axes[1, 0]
ax3_twin = ax3.twinx()

bar_positions = np.arange(len(order_data['orders']))
bars = ax3.bar(bar_positions, order_data['heights'], color='#1abc9c',
               edgecolor='black', linewidth=0.5, alpha=0.7, label='Tree Height')
line = ax3_twin.plot(bar_positions, np.array(order_data['search_ops'])/1e6,
                     'D-', color='#e67e22', linewidth=2, markersize=8, label='Search Throughput')

ax3.set_xlabel('B-tree Order (Max Children per Node)')
ax3.set_ylabel('Tree Height', color='#1abc9c')
ax3_twin.set_ylabel('Search Throughput (M ops/sec)', color='#e67e22')
ax3.set_title('Effect of B-tree Order on Performance\n(100K records)', fontweight='bold')
ax3.set_xticks(bar_positions)
ax3.set_xticklabels(order_data['orders'])
ax3.tick_params(axis='y', labelcolor='#1abc9c')
ax3_twin.tick_params(axis='y', labelcolor='#e67e22')

# Combined legend
lines1, labels1 = ax3.get_legend_handles_labels()
lines2, labels2 = ax3_twin.get_legend_handles_labels()
ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

# Highlight optimal range
ax3.axvspan(4, 6, alpha=0.2, color='green', label='Optimal Range')
ax3.annotate('Optimal\n(Order 64-256)', xy=(5, 6), fontsize=9, ha='center',
             color='darkgreen', fontweight='bold')

# ============== Plot 4: Speedup Factor ==============
ax4 = axes[1, 1]

speedups = [l/b for l, b in zip(btree_linear_data['linear_comparisons'],
                                 btree_linear_data['btree_comparisons'])]

bars = ax4.bar(range(len(btree_linear_data['sizes'])), speedups,
               color='#3498db', edgecolor='black', linewidth=0.5)

ax4.set_xlabel('Dataset Size')
ax4.set_ylabel('Speedup Factor (x times fewer comparisons)')
ax4.set_title('B-tree Advantage: Comparison Reduction\n(Higher is Better)', fontweight='bold')
ax4.set_xticks(range(len(btree_linear_data['sizes'])))
ax4.set_xticklabels([f'{s:,}' for s in btree_linear_data['sizes']])

# Add value labels
for i, (bar, speedup) in enumerate(zip(bars, speedups)):
    height = bar.get_height()
    ax4.annotate(f'{speedup:.0f}x',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=10, fontweight='bold')

# Add exponential trend indicator
ax4.set_yscale('log')
ax4.axhline(y=1000, color='red', linestyle='--', alpha=0.5)
ax4.annotate('1000x threshold', xy=(4, 1000), fontsize=9, color='red', va='bottom')

# Adjust layout
plt.tight_layout()
plt.suptitle('SQLite B-tree Indexing Performance Analysis', fontsize=14, fontweight='bold', y=1.02)

# Save figure
output_path = 'assets/btree_benchmark_results.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
print(f"Saved visualization to: {output_path}")

# Also create a simpler summary chart
fig2, ax = plt.subplots(figsize=(10, 6))

# Comparison reduction visualization
sizes = btree_linear_data['sizes']
btree_comps = btree_linear_data['btree_comparisons']
linear_comps = btree_linear_data['linear_comparisons']

x = np.arange(len(sizes))
width = 0.35

bars1 = ax.bar(x - width/2, btree_comps, width, label='B-tree (O(log N))',
               color='#27ae60', edgecolor='black')
bars2 = ax.bar(x + width/2, linear_comps, width, label='Linear Scan (O(N))',
               color='#c0392b', edgecolor='black')

ax.set_ylabel('Comparisons per Search (log scale)')
ax.set_xlabel('Number of Records')
ax.set_title('B-tree vs Linear Search: Why Indexes Matter', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels([f'{s:,}' for s in sizes])
ax.set_yscale('log')
ax.legend()

# Add speedup annotations
for i, (b, l) in enumerate(zip(btree_comps, linear_comps)):
    speedup = l / b
    ax.annotate(f'{speedup:.0f}x\nfaster',
                xy=(i, max(b, l) * 1.5),
                ha='center', fontsize=9, fontweight='bold', color='#2c3e50')

plt.tight_layout()
output_path2 = 'assets/btree_vs_linear.png'
plt.savefig(output_path2, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
print(f"Saved visualization to: {output_path2}")

print("\nVisualization complete!")
