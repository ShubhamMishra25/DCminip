"""
Concurrent Bid Test — sends simultaneous bid requests to the gRPC server
to demonstrate concurrency handling and synchronization.

Usage:
    python concurrent_bid_test.py

This script:
1. Registers multiple test users.
2. Creates a test auction.
3. Sends N simultaneous bid requests via gRPC.
4. Verifies that the highest bid is correct (no race conditions).
5. Logs thread IDs and timestamps.
"""

import sys
import os
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import grpc
from generated import auction_pb2, auction_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Thread-%(thread)d | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("concurrent-test")

SERVER_ADDRESS = "localhost:50051"
NUM_BIDDERS = 5
STARTING_PRICE = 100.0


def create_stub():
    """Create a gRPC channel and stub."""
    channel = grpc.insecure_channel(SERVER_ADDRESS)
    return auction_pb2_grpc.AuctionServiceStub(channel), channel


def register_and_login(stub, username, password, role):
    """Register a user and login, returning the token."""
    # Register
    reg_resp = stub.RegisterUser(
        auction_pb2.RegisterRequest(username=username, password=password, role=role)
    )
    logger.info(f"Register {username}: {reg_resp.message}")

    # Login
    login_resp = stub.Login(
        auction_pb2.LoginRequest(username=username, password=password)
    )
    logger.info(f"Login {username}: {login_resp.message}")
    return login_resp.token, login_resp.user_id


def bid_worker(bidder_index, auction_id, token, bid_amount):
    """Worker function for placing a bid from a separate thread."""
    thread_id = threading.current_thread().ident
    stub, channel = create_stub()

    logger.info(
        f"[Bidder-{bidder_index}] Placing bid ${bid_amount:.2f} "
        f"on auction {auction_id[:8]}..."
    )

    try:
        response = stub.PlaceBid(
            auction_pb2.PlaceBidRequest(
                token=token,
                auction_id=auction_id,
                bid_amount=bid_amount,
            ),
            timeout=10,  # RPC deadline
        )
        status = "[ACCEPTED]" if response.success else "[REJECTED]"
        logger.info(
            f"[Bidder-{bidder_index}] {status} - "
            f"${bid_amount:.2f} | Server thread: {response.thread_id} | "
            f"Highest: ${response.current_highest_bid:.2f}"
        )
        return {
            "bidder": f"Bidder-{bidder_index}",
            "amount": bid_amount,
            "success": response.success,
            "message": response.message,
            "server_thread": response.thread_id,
        }
    except grpc.RpcError as e:
        logger.error(f"[Bidder-{bidder_index}] RPC Error: {e.code()} — {e.details()}")
        return {
            "bidder": f"Bidder-{bidder_index}",
            "amount": bid_amount,
            "success": False,
            "message": str(e),
            "server_thread": "",
        }
    finally:
        channel.close()


def run_concurrent_test():
    """Main concurrent bidding test."""
    logger.info("=" * 60)
    logger.info("  CONCURRENT BID TEST")
    logger.info("=" * 60)

    stub, channel = create_stub()
    timestamp = str(int(time.time()))

    # 1. Register seller and create auction
    logger.info("\n--- Registering test users ---")
    seller_token, _ = register_and_login(
        stub, f"seller_{timestamp}", "pass1234", "seller"
    )

    # Register bidders
    bidder_tokens = []
    for i in range(NUM_BIDDERS):
        token, _ = register_and_login(
            stub, f"bidder_{i}_{timestamp}", "pass1234", "buyer"
        )
        bidder_tokens.append(token)

    # 2. Create auction
    logger.info("\n--- Creating test auction ---")
    create_resp = stub.CreateAuction(
        auction_pb2.CreateAuctionRequest(
            token=seller_token,
            item_name=f"Concurrent Test Item {timestamp}",
            description="Item for concurrent bidding test",
            starting_price=STARTING_PRICE,
            duration_seconds=600,
        )
    )
    auction_id = create_resp.auction_id
    logger.info(f"Auction created: {auction_id}")

    # 3. Send simultaneous bids
    logger.info(f"\n--- Sending {NUM_BIDDERS} simultaneous bids ---")
    logger.info("All threads will start bidding at the same time...")

    barrier = threading.Barrier(NUM_BIDDERS)
    results = []
    results_lock = threading.Lock()

    def synchronized_bid(i, token, amount):
        """Wait for all threads, then bid."""
        barrier.wait()
        result = bid_worker(i, auction_id, token, amount)
        with results_lock:
            results.append(result)

    threads = []
    for i in range(NUM_BIDDERS):
        bid_amount = STARTING_PRICE + (i + 1) * 25  # 125, 150, 175, 200, 225
        t = threading.Thread(
            target=synchronized_bid,
            args=(i, bidder_tokens[i], bid_amount),
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=15)

    # 4. Verify final state
    logger.info("\n--- Verifying final state ---")
    highest_resp = stub.GetHighestBid(
        auction_pb2.GetHighestBidRequest(token=bidder_tokens[0], auction_id=auction_id)
    )

    expected_highest = STARTING_PRICE + NUM_BIDDERS * 25
    actual_highest = highest_resp.highest_bid

    logger.info(f"Expected highest bid: ${expected_highest:.2f}")
    logger.info(f"Actual highest bid:   ${actual_highest:.2f}")
    logger.info(f"Highest bidder:       {highest_resp.highest_bidder}")

    if actual_highest == expected_highest:
        logger.info("[PASSED] Synchronization is working correctly!")
    else:
        logger.warning("[FAILED] Possible race condition detected!")

    # 5. Print bid history
    logger.info("\n--- Bid History ---")
    history_resp = stub.GetBidHistory(
        auction_pb2.GetBidHistoryRequest(token=bidder_tokens[0], auction_id=auction_id)
    )
    for bid in history_resp.bids:
        logger.info(
            f"  {bid.bidder_username}: ${bid.bid_amount:.2f} "
            f"(Thread: {bid.thread_id})"
        )

    channel.close()
    logger.info("\n" + "=" * 60)
    logger.info("  TEST COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_concurrent_test()
