"""
Synchronized Bidding Demonstration Module.

Demonstrates how mutual exclusion with threading.Lock guarantees
atomic read-validate-update operations, preventing race conditions
even under heavy concurrent bidding.

Usage:
    python synchronized_demo.py
"""

import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import Database
from concurrency.race_condition_demo import RaceConditionDemo

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = Database()
    demo = RaceConditionDemo(db)
    print("\n>>> RUNNING DEMO WITH SYNCHRONIZATION (DEMONSTRATING MUTUAL EXCLUSION) <<<")
    result = demo.run_demo(num_concurrent_bids=10, use_locks=True)
    print(result["report"])
