"""
Bidding service for the Online Auction System.
Handles bid placement with per-auction locking for thread safety.

KEY DISTRIBUTED COMPUTING CONCEPTS:
- Per-auction locks (threading.Lock) ensure mutual exclusion
- Only one thread can modify an auction's highest bid at a time
- The read-validate-update operation is atomic within the lock
"""

import threading
import time
import logging

logger = logging.getLogger(__name__)


class BiddingService:
    """
    Manages bid placement with synchronization.
    
    Uses per-auction locks to ensure mutual exclusion when validating
    and updating bids. This prevents race conditions where two concurrent
    bids might both read the same highest bid and both think they are valid.
    """

    def __init__(self, db):
        self.db = db
        # Per-auction locks: each auction gets its own lock
        self._auction_locks = {}
        # Lock for managing the auction_locks dictionary itself
        self._locks_lock = threading.Lock()
        # Subscribers for bid updates (auction_id -> list of queues)
        self._subscribers = {}
        self._subscribers_lock = threading.Lock()

    def _get_auction_lock(self, auction_id):
        """
        Get or create a lock for a specific auction.
        Uses double-checked locking pattern for efficiency.
        """
        if auction_id not in self._auction_locks:
            with self._locks_lock:
                if auction_id not in self._auction_locks:
                    self._auction_locks[auction_id] = threading.Lock()
                    logger.info(f"[SYNC] Created lock for auction {auction_id}")
        return self._auction_locks[auction_id]

    def place_bid(self, auction_id, bidder_id, bidder_username, bid_amount):
        """
        Place a bid with full synchronization.

        CRITICAL SECTION: The read-validate-update sequence is protected
        by a per-auction lock to prevent race conditions.

        Flow:
        1. Acquire per-auction lock
        2. Read current highest bid
        3. Validate new bid > current highest bid
        4. Update auction with new bid
        5. Release lock

        Returns: (success, message, current_highest_bid, highest_bidder, thread_id, timestamp)
        """
        thread_id = str(threading.current_thread().ident)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(
            f"[BID] Thread {thread_id} attempting bid ${bid_amount:.2f} "
            f"on auction {auction_id} at {timestamp}"
        )

        lock = self._get_auction_lock(auction_id)

        # ═══════════════════════════════════════════════════════════════
        # CRITICAL SECTION — Protected by per-auction lock
        # ═══════════════════════════════════════════════════════════════
        lock.acquire()
        logger.info(f"[SYNC] Thread {thread_id} ACQUIRED lock for auction {auction_id}")

        try:
            # Step 1: Read current state
            auction = self.db.get_auction(auction_id)
            if not auction:
                return False, "Auction not found", 0, "", thread_id, timestamp

            if auction["status"] != "active":
                return False, "Auction is closed", 0, "", thread_id, timestamp

            if auction["seller_id"] == bidder_id:
                return False, "Sellers cannot bid on their own auctions", 0, "", thread_id, timestamp

            current_highest = auction["current_highest_bid"]

            # Step 2: Validate bid
            if bid_amount <= current_highest:
                logger.warning(
                    f"[BID] Thread {thread_id} bid ${bid_amount:.2f} rejected "
                    f"(current highest: ${current_highest:.2f})"
                )
                return (
                    False,
                    f"Bid must be higher than current highest bid (${current_highest:.2f})",
                    current_highest,
                    auction.get("highest_bidder_username", ""),
                    thread_id,
                    timestamp,
                )

            # Step 3: Update atomically
            success, message, bid_id = self.db.update_auction_bid(
                auction_id, bid_amount, bidder_id, bidder_username, thread_id
            )

            if success:
                logger.info(
                    f"[BID] Thread {thread_id} bid ${bid_amount:.2f} ACCEPTED "
                    f"on auction {auction_id}"
                )
                # Notify subscribers
                self._notify_subscribers(auction_id, bid_amount, bidder_username)
                return True, "Bid placed successfully", bid_amount, bidder_username, thread_id, timestamp
            else:
                return False, message, current_highest, "", thread_id, timestamp

        finally:
            lock.release()
            logger.info(f"[SYNC] Thread {thread_id} RELEASED lock for auction {auction_id}")
        # ═══════════════════════════════════════════════════════════════
        # END CRITICAL SECTION
        # ═══════════════════════════════════════════════════════════════

    def subscribe(self, auction_id):
        """
        Subscribe to bid updates for an auction.
        Returns a queue that will receive BidUpdate messages.
        """
        import queue
        q = queue.Queue()
        with self._subscribers_lock:
            if auction_id not in self._subscribers:
                self._subscribers[auction_id] = []
            self._subscribers[auction_id].append(q)
            logger.info(f"[STREAM] New subscriber for auction {auction_id} (total: {len(self._subscribers[auction_id])})")
        return q

    def unsubscribe(self, auction_id, q):
        """Remove a subscriber queue."""
        with self._subscribers_lock:
            if auction_id in self._subscribers:
                try:
                    self._subscribers[auction_id].remove(q)
                    logger.info(f"[STREAM] Subscriber removed for auction {auction_id}")
                except ValueError:
                    pass

    def _notify_subscribers(self, auction_id, bid_amount, bidder_username):
        """Notify all subscribers of a new bid."""
        with self._subscribers_lock:
            if auction_id in self._subscribers:
                auction = self.db.get_auction(auction_id)
                update = {
                    "auction_id": auction_id,
                    "new_highest_bid": bid_amount,
                    "highest_bidder": bidder_username,
                    "timestamp": int(time.time()),
                    "total_bids": auction["total_bids"] if auction else 0,
                    "bidder_username": bidder_username,
                }
                dead_queues = []
                for q in self._subscribers[auction_id]:
                    try:
                        q.put_nowait(update)
                    except Exception:
                        dead_queues.append(q)
                for q in dead_queues:
                    self._subscribers[auction_id].remove(q)
                logger.info(
                    f"[STREAM] Notified {len(self._subscribers[auction_id])} "
                    f"subscribers for auction {auction_id}"
                )
