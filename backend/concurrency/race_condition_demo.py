"""
Race Condition Demonstration Module.

This module demonstrates the critical distributed computing concept of
race conditions in a concurrent auction system.

TWO MODES:
1. WITHOUT LOCKS: Multiple threads read-then-write the highest bid
   without synchronization. A deliberate delay between read and write
   amplifies the race condition window, causing incorrect final state.

2. WITH LOCKS: The same operations are protected by threading.Lock,
   ensuring atomic read-validate-update. The final bid is always correct.
"""

import threading
import time
import logging
import uuid

logger = logging.getLogger(__name__)


class RaceConditionDemo:
    """Demonstrates race conditions with and without synchronization."""

    def __init__(self, db):
        self.db = db

    def run_demo(self, num_concurrent_bids=10, use_locks=False):
        """
        Run the race condition demonstration.
        
        Args:
            num_concurrent_bids: Number of concurrent bid threads to spawn.
            use_locks: If True, use threading.Lock for synchronization.
            
        Returns:
            dict with report, expected/actual highest bid, and logs.
        """
        logs = []
        lock = threading.Lock() if use_locks else None
        mode = "WITH LOCKS" if use_locks else "WITHOUT LOCKS"

        logs.append(f"{'='*60}")
        logs.append(f"  RACE CONDITION DEMO - {mode}")
        logs.append(f"  Concurrent bids: {num_concurrent_bids}")
        logs.append(f"{'='*60}")

        # Create a demo auction
        starting_price = 100.0
        auction_id = self.db.create_demo_auction(starting_price)
        logs.append(f"Created demo auction: {auction_id}")
        logs.append(f"Starting price: ${starting_price:.2f}")
        logs.append("")

        # Each bidder will bid $10 more than the starting price + their index
        # Expected final: starting_price + num_concurrent_bids * 10
        results = {"bids_attempted": 0, "bids_accepted": 0, "errors": []}
        results_lock = threading.Lock()
        barrier = threading.Barrier(num_concurrent_bids)

        def bid_worker(bidder_index):
            """Worker thread for placing a bid."""
            thread_id = threading.current_thread().ident
            bidder_name = f"Bidder-{bidder_index}"
            bid_amount = starting_price + (bidder_index + 1) * 10  # 110, 120, 130, ...

            try:
                # Synchronize all threads to start at the same time
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass

            log_entry = (
                f"[Thread {thread_id}] {bidder_name} attempting bid "
                f"${bid_amount:.2f}"
            )
            logger.info(log_entry)

            if use_locks:
                # ──── WITH SYNCHRONIZATION ────
                lock.acquire()
                log_entry = f"[Thread {thread_id}] {bidder_name} ACQUIRED lock"
                logger.info(log_entry)
                with results_lock:
                    logs.append(log_entry)

                try:
                    # Read current highest bid
                    auction = self.db.get_auction(auction_id)
                    current_highest = auction["current_highest_bid"]
                    log_entry = (
                        f"[Thread {thread_id}] {bidder_name} reads highest bid: "
                        f"${current_highest:.2f}"
                    )
                    logger.info(log_entry)
                    with results_lock:
                        logs.append(log_entry)

                    # Validate
                    if bid_amount > current_highest:
                        # Controlled delay to demonstrate what would be a race window
                        time.sleep(0.05)

                        # Update
                        self.db.update_demo_bid_unsafe(
                            auction_id, bid_amount, bidder_name, str(thread_id)
                        )
                        log_entry = (
                            f"[Thread {thread_id}] {bidder_name} bid ${bid_amount:.2f} "
                            f"ACCEPTED (was ${current_highest:.2f})"
                        )
                        logger.info(log_entry)
                        with results_lock:
                            logs.append(log_entry)
                            results["bids_accepted"] += 1
                    else:
                        log_entry = (
                            f"[Thread {thread_id}] {bidder_name} bid ${bid_amount:.2f} "
                            f"REJECTED (current: ${current_highest:.2f})"
                        )
                        logger.info(log_entry)
                        with results_lock:
                            logs.append(log_entry)
                finally:
                    lock.release()
                    log_entry = f"[Thread {thread_id}] {bidder_name} RELEASED lock"
                    logger.info(log_entry)
                    with results_lock:
                        logs.append(log_entry)
            else:
                # ──── WITHOUT SYNCHRONIZATION (RACE CONDITION) ────
                # Read current highest bid
                auction = self.db.get_auction(auction_id)
                current_highest = auction["current_highest_bid"]
                log_entry = (
                    f"[Thread {thread_id}] {bidder_name} reads highest bid: "
                    f"${current_highest:.2f}"
                )
                logger.info(log_entry)
                with results_lock:
                    logs.append(log_entry)

                # Validate (no lock — all threads may see the same value!)
                if bid_amount > current_highest:
                    # Deliberate delay to widen the race window
                    # Multiple threads will read the SAME highest bid, all pass
                    # validation, and all write — but only the last write wins,
                    # potentially allowing a LOWER bid to overwrite a HIGHER one.
                    time.sleep(0.1)

                    # Update (no lock)
                    self.db.update_demo_bid_unsafe(
                        auction_id, bid_amount, bidder_name, str(thread_id)
                    )
                    log_entry = (
                        f"[Thread {thread_id}] {bidder_name} bid ${bid_amount:.2f} "
                        f"ACCEPTED (was ${current_highest:.2f}) [!] NO LOCK"
                    )
                    logger.info(log_entry)
                    with results_lock:
                        logs.append(log_entry)
                        results["bids_accepted"] += 1
                else:
                    log_entry = (
                        f"[Thread {thread_id}] {bidder_name} bid ${bid_amount:.2f} "
                        f"REJECTED (current: ${current_highest:.2f})"
                    )
                    logger.info(log_entry)
                    with results_lock:
                        logs.append(log_entry)

            with results_lock:
                results["bids_attempted"] += 1

        # Launch all bid threads
        threads = []
        for i in range(num_concurrent_bids):
            t = threading.Thread(target=bid_worker, args=(i,), name=f"BidWorker-{i}")
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=10)

        # Check final state
        final_auction = self.db.get_auction(auction_id)
        actual_highest = final_auction["current_highest_bid"]
        expected_highest = starting_price + num_concurrent_bids * 10

        race_detected = actual_highest != expected_highest

        logs.append("")
        logs.append(f"{'-'*60}")
        logs.append(f"  RESULTS")
        logs.append(f"{'-'*60}")
        logs.append(f"  Bids attempted: {results['bids_attempted']}")
        logs.append(f"  Bids accepted:  {results['bids_accepted']}")
        logs.append(f"  Expected highest bid: ${expected_highest:.2f}")
        logs.append(f"  Actual highest bid:   ${actual_highest:.2f}")
        logs.append(f"  Race condition detected: {'YES [!]' if race_detected else 'NO [OK]'}")

        if race_detected:
            logs.append("")
            logs.append("  [!] RACE CONDITION EXPLANATION:")
            logs.append("  Multiple threads read the same highest bid value before")
            logs.append("  any of them wrote their update. This caused multiple threads")
            logs.append("  to pass validation simultaneously. The last thread to write")
            logs.append("  'won', but it may have been a LOWER bid than one that was")
            logs.append("  already accepted, leading to an INCORRECT final state.")
        else:
            logs.append("")
            logs.append("  [OK] MUTUAL EXCLUSION WORKING CORRECTLY")
            logs.append("  The lock ensured that only one thread could read-validate-")
            logs.append("  update the highest bid at a time. Each thread saw the true")
            logs.append("  current highest bid after the previous thread's update.")

        logs.append(f"{'='*60}")

        report = "\n".join(logs)
        logger.info(f"\n{report}")

        # Clean up demo auction
        self.db.delete_demo_auction(auction_id)

        return {
            "report": report,
            "expected_highest_bid": expected_highest,
            "actual_highest_bid": actual_highest,
            "race_condition_detected": race_detected,
            "logs": logs,
        }


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database.db import Database

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = Database()
    demo = RaceConditionDemo(db)
    print("\n>>> RUNNING DEMO WITHOUT SYNCHRONIZATION (DEMONSTRATING RACE CONDITION) <<<")
    result = demo.run_demo(num_concurrent_bids=10, use_locks=False)
    print(result["report"])

