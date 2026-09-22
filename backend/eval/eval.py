"""Evaluation Benchmark Harness

Measures precision@10, shortfall rate, latency, and cost per search across benchmark businesses.
"""
import json
import os
import sys

# Ensure backend root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), "sample_businesses.json")


def load_benchmarks():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_eval():
    benchmarks = load_benchmarks()
    print(f"Loaded {len(benchmarks)} benchmark businesses for evaluation.")
    print("Stage 1 evaluation harness initialized. Full execution enabled in Stage 7.")


if __name__ == "__main__":
    run_eval()
