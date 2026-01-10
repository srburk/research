#!/usr/bin/env python3
"""
B-Tree Test Suite Generator

Generates test data and validation scripts for the B-tree benchmark.
Provides:
1. Random test data generation
2. Expected results calculation
3. Benchmark result analysis
4. Performance visualization

Usage:
    python3 generate_tests.py              # Generate test data
    python3 generate_tests.py --analyze    # Analyze benchmark results
    python3 generate_tests.py --visualize  # Generate charts (requires matplotlib)
"""

import argparse
import json
import os
import random
import sys
import time
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TestCase:
    """Represents a single test case."""
    name: str
    keys: List[int]
    operations: List[Tuple[str, int]]  # (operation_type, key)
    expected_results: Dict[str, any]


@dataclass
class BenchmarkResult:
    """Parsed benchmark result."""
    name: str
    records: int
    order: int
    insert_time_ms: float
    insert_ops_per_sec: float
    search_ops_per_sec: float
    height: int
    avg_comparisons: float
    avg_node_visits: float
    fill_factor: float


class TestDataGenerator:
    """Generates test data for B-tree benchmarks."""

    def __init__(self, seed: int = 42):
        """Initialize with a random seed for reproducibility."""
        self.seed = seed
        random.seed(seed)

    def generate_sequential_keys(self, count: int, start: int = 1) -> List[int]:
        """Generate sequential keys."""
        return list(range(start, start + count))

    def generate_random_keys(self, count: int, min_val: int = 1,
                            max_val: int = 10**9) -> List[int]:
        """Generate unique random keys."""
        keys = set()
        while len(keys) < count:
            keys.add(random.randint(min_val, max_val))
        return list(keys)

    def generate_skewed_keys(self, count: int, skew_factor: float = 0.8) -> List[int]:
        """Generate keys with Zipfian-like distribution."""
        keys = []
        max_val = count * 10
        for _ in range(count):
            if random.random() < skew_factor:
                # Hot keys (small range)
                keys.append(random.randint(1, count // 10))
            else:
                # Cold keys (larger range)
                keys.append(random.randint(count // 10, max_val))
        return list(set(keys))[:count]

    def generate_operations(self, keys: List[int],
                           search_ratio: float = 0.7,
                           insert_ratio: float = 0.2,
                           delete_ratio: float = 0.1,
                           count: int = 10000) -> List[Tuple[str, int]]:
        """Generate mixed operations with specified ratios."""
        operations = []
        for _ in range(count):
            r = random.random()
            key = random.choice(keys)
            if r < search_ratio:
                operations.append(('search', key))
            elif r < search_ratio + insert_ratio:
                new_key = random.randint(1, max(keys) * 2)
                operations.append(('insert', new_key))
            else:
                operations.append(('delete', key))
        return operations


class TestCaseBuilder:
    """Builds test cases with expected results."""

    def __init__(self, generator: TestDataGenerator):
        self.generator = generator

    def calculate_expected_height(self, n: int, order: int) -> int:
        """Calculate expected B-tree height."""
        if n == 0:
            return 0
        # height = ceil(log_order(n))
        return max(1, math.ceil(math.log(n + 1) / math.log(order)))

    def calculate_expected_comparisons(self, n: int, order: int) -> float:
        """Calculate expected comparisons per search."""
        height = self.calculate_expected_height(n, order)
        # Binary search within each node: log2(keys_per_node)
        keys_per_node = order - 1
        comparisons_per_node = math.log2(keys_per_node) if keys_per_node > 1 else 1
        return height * comparisons_per_node

    def build_scaling_test(self, sizes: List[int], order: int = 128) -> List[TestCase]:
        """Build test cases for scaling analysis."""
        test_cases = []
        for size in sizes:
            keys = self.generator.generate_random_keys(size)
            operations = self.generator.generate_operations(keys, count=min(10000, size))

            expected = {
                'height': self.calculate_expected_height(size, order),
                'avg_comparisons_upper_bound': self.calculate_expected_comparisons(size, order) * 1.5,
                'search_complexity': 'O(log n)',
            }

            test_case = TestCase(
                name=f"scaling_test_{size}",
                keys=keys,
                operations=operations,
                expected_results=expected
            )
            test_cases.append(test_case)

        return test_cases

    def build_correctness_test(self, size: int = 1000) -> TestCase:
        """Build a correctness verification test."""
        keys = self.generator.generate_sequential_keys(size)
        random.shuffle(keys)

        operations = []
        # Insert all keys
        for key in keys:
            operations.append(('insert', key))
        # Search for all keys (should all succeed)
        for key in keys:
            operations.append(('search', key))
        # Search for non-existent keys
        for i in range(100):
            operations.append(('search_missing', size + i + 1))

        expected = {
            'all_inserts_succeed': True,
            'all_searches_find': True,
            'missing_searches_fail': True,
        }

        return TestCase(
            name="correctness_test",
            keys=keys,
            operations=operations,
            expected_results=expected
        )


class BenchmarkAnalyzer:
    """Analyzes benchmark results."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    def parse_results_file(self, filepath: str) -> None:
        """Parse benchmark output file."""
        with open(filepath, 'r') as f:
            lines = f.readlines()

        for line in lines:
            if '|' in line and not line.startswith('-'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 10 and parts[0] and not parts[0].startswith('Benchmark'):
                    try:
                        result = BenchmarkResult(
                            name=parts[0],
                            records=int(parts[1]) if parts[1].isdigit() else 0,
                            order=int(parts[2]) if parts[2].isdigit() else 0,
                            insert_time_ms=float(parts[3]) if parts[3].replace('.', '').isdigit() else 0,
                            insert_ops_per_sec=float(parts[4]) if parts[4].replace('.', '').isdigit() else 0,
                            search_ops_per_sec=float(parts[5]) if parts[5].replace('.', '').isdigit() else 0,
                            height=int(parts[6]) if parts[6].isdigit() else 0,
                            avg_comparisons=float(parts[7]) if parts[7].replace('.', '').isdigit() else 0,
                            avg_node_visits=float(parts[8]) if parts[8].replace('.', '').isdigit() else 0,
                            fill_factor=float(parts[9].rstrip('%')) / 100 if '%' in parts[9] else 0,
                        )
                        self.results.append(result)
                    except (ValueError, IndexError):
                        continue

    def generate_analysis_report(self) -> str:
        """Generate analysis report."""
        if not self.results:
            return "No results to analyze."

        report = []
        report.append("=" * 60)
        report.append("B-TREE BENCHMARK ANALYSIS REPORT")
        report.append("=" * 60)
        report.append("")

        # Group by test type
        btree_results = [r for r in self.results if 'B-tree' in r.name or 'Order=' in r.name]
        linear_results = [r for r in self.results if 'Linear' in r.name]

        # Scaling analysis
        scaling_results = [r for r in btree_results if 'n=' in r.name]
        if scaling_results:
            report.append("SCALING ANALYSIS")
            report.append("-" * 40)
            for r in scaling_results:
                theoretical_height = math.ceil(math.log(r.records + 1) / math.log(r.order)) if r.order > 1 else 0
                report.append(f"Records: {r.records:,}")
                report.append(f"  Actual Height: {r.height}, Theoretical: {theoretical_height}")
                report.append(f"  Search throughput: {r.search_ops_per_sec:,.0f} ops/sec")
                report.append(f"  Avg comparisons: {r.avg_comparisons:.2f}")
                report.append("")

        # B-tree vs Linear comparison
        if linear_results:
            report.append("B-TREE vs LINEAR COMPARISON")
            report.append("-" * 40)

            for linear in linear_results:
                size_str = linear.name.split('=')[1].rstrip(')')
                matching_btree = next(
                    (r for r in btree_results if f'n={size_str}' in r.name), None
                )
                if matching_btree:
                    speedup = linear.avg_comparisons / matching_btree.avg_comparisons if matching_btree.avg_comparisons > 0 else 0
                    report.append(f"Dataset size: {size_str}")
                    report.append(f"  B-tree comparisons: {matching_btree.avg_comparisons:.2f}")
                    report.append(f"  Linear comparisons: {linear.avg_comparisons:.2f}")
                    report.append(f"  Comparison reduction: {speedup:.1f}x")
                    report.append("")

        # Order comparison
        order_results = [r for r in btree_results if r.name.startswith('Order=')]
        if order_results:
            report.append("ORDER (FANOUT) COMPARISON")
            report.append("-" * 40)
            best_throughput = max(order_results, key=lambda r: r.search_ops_per_sec)
            best_height = min(order_results, key=lambda r: r.height)

            report.append(f"Best search throughput: Order={best_throughput.order} ({best_throughput.search_ops_per_sec:,.0f} ops/sec)")
            report.append(f"Minimum height: Order={best_height.order} (height={best_height.height})")
            report.append("")

        report.append("=" * 60)
        report.append("END OF REPORT")
        report.append("=" * 60)

        return "\n".join(report)

    def validate_complexity(self) -> Dict[str, bool]:
        """Validate that B-tree operations exhibit O(log n) complexity."""
        btree_results = [r for r in self.results if 'B-tree' in r.name and 'n=' in r.name]
        if len(btree_results) < 2:
            return {'valid': False, 'reason': 'Insufficient data points'}

        # Sort by record count
        btree_results.sort(key=lambda r: r.records)

        # Check that comparisons grow logarithmically
        # For O(log n), doubling n should add a constant to comparisons
        validations = {}

        for i in range(1, len(btree_results)):
            prev = btree_results[i - 1]
            curr = btree_results[i]

            if prev.records > 0 and curr.records > 0:
                size_ratio = curr.records / prev.records
                comp_ratio = curr.avg_comparisons / prev.avg_comparisons if prev.avg_comparisons > 0 else 0

                # For log n growth, comp_ratio should be much smaller than size_ratio
                is_logarithmic = comp_ratio < math.sqrt(size_ratio) if size_ratio > 1 else True
                validations[f'{prev.records}->{curr.records}'] = is_logarithmic

        all_valid = all(validations.values())
        return {
            'valid': all_valid,
            'details': validations,
            'conclusion': 'B-tree demonstrates O(log n) search complexity' if all_valid
                         else 'Complexity validation failed - check results'
        }


def save_test_data(test_cases: List[TestCase], output_dir: str) -> None:
    """Save test cases to JSON files."""
    os.makedirs(output_dir, exist_ok=True)

    for tc in test_cases:
        filepath = os.path.join(output_dir, f"{tc.name}.json")
        data = {
            'name': tc.name,
            'keys': tc.keys,
            'operations': tc.operations,
            'expected_results': tc.expected_results
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description='B-Tree Test Suite Generator and Analyzer'
    )
    parser.add_argument('--analyze', type=str, metavar='FILE',
                       help='Analyze benchmark results file')
    parser.add_argument('--generate', action='store_true',
                       help='Generate test data (default action)')
    parser.add_argument('--output', type=str, default='tests/data',
                       help='Output directory for test data')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility')
    parser.add_argument('--validate', type=str, metavar='FILE',
                       help='Validate benchmark results against expected complexity')

    args = parser.parse_args()

    if args.analyze:
        print("Analyzing benchmark results...")
        analyzer = BenchmarkAnalyzer()
        analyzer.parse_results_file(args.analyze)
        report = analyzer.generate_analysis_report()
        print(report)

        # Save report
        report_path = args.analyze.replace('.txt', '_analysis.txt')
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")

    elif args.validate:
        print("Validating benchmark results...")
        analyzer = BenchmarkAnalyzer()
        analyzer.parse_results_file(args.validate)
        validation = analyzer.validate_complexity()

        print("\nComplexity Validation Results:")
        print("-" * 40)
        print(f"Overall valid: {validation['valid']}")
        if 'details' in validation:
            for key, value in validation['details'].items():
                status = "PASS" if value else "FAIL"
                print(f"  {key}: {status}")
        print(f"\nConclusion: {validation.get('conclusion', 'N/A')}")

    else:
        # Default: generate test data
        print("Generating B-tree test data...")
        generator = TestDataGenerator(seed=args.seed)
        builder = TestCaseBuilder(generator)

        # Generate different test suites
        test_cases = []

        # Scaling tests
        scaling_sizes = [1000, 5000, 10000, 50000, 100000]
        test_cases.extend(builder.build_scaling_test(scaling_sizes))

        # Correctness test
        test_cases.append(builder.build_correctness_test(size=1000))

        # Save test data
        save_test_data(test_cases, args.output)

        print(f"\nGenerated {len(test_cases)} test cases.")
        print(f"Test data saved to: {args.output}/")

        # Print summary
        print("\nTest Case Summary:")
        print("-" * 40)
        for tc in test_cases:
            print(f"  {tc.name}:")
            print(f"    Keys: {len(tc.keys)}")
            print(f"    Operations: {len(tc.operations)}")
            print(f"    Expected height: {tc.expected_results.get('height', 'N/A')}")


if __name__ == '__main__':
    main()
