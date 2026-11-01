"""
Online Auction System – gRPC Server Entry Point.

Starts the gRPC server with a ThreadPoolExecutor for handling
concurrent requests from multiple clients.

DISTRIBUTED COMPUTING CONCEPTS DEMONSTRATED:
- ThreadPoolExecutor: handles concurrent RPC requests
- Per-auction locks: mutual exclusion for bid operations
- gRPC server streaming: real-time bid updates
- Protocol Buffers: serialization/deserialization
"""

import sys
import os
import logging
from concurrent import futures

import grpc
from grpc_reflection.v1alpha import reflection

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from generated import auction_pb2, auction_pb2_grpc
from server.auction_service import AuctionServiceServicer
from server.auction_manager import AuctionManager
from services.auth_service import AuthService
from services.bidding_service import BiddingService
from database.db import Database

# ─── Logging Configuration ────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("auction-server")

# ─── Server Configuration ─────────────────────────────────────────────────────

SERVER_PORT = 50051
MAX_WORKERS = 100  # Scalable ThreadPoolExecutor for concurrent requests & streaming


def serve():
    """Start the gRPC auction server."""
    logger.info("=" * 60)
    logger.info("  ONLINE AUCTION SYSTEM – gRPC Server")
    logger.info("=" * 60)

    # Initialize layers
    logger.info("[INIT] Initializing database...")
    db = Database()

    logger.info("[INIT] Initializing services...")
    auth_service = AuthService(db)
    bidding_service = BiddingService(db)

    logger.info("[INIT] Initializing auction manager...")
    auction_manager = AuctionManager(db, auth_service, bidding_service)

    # Create gRPC server with ThreadPoolExecutor
    logger.info(f"[INIT] Creating gRPC server with ThreadPoolExecutor (max_workers={MAX_WORKERS})...")
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=MAX_WORKERS),
        options=[
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
        ],
    )

    # Register service
    servicer = AuctionServiceServicer(auction_manager, db)
    auction_pb2_grpc.add_AuctionServiceServicer_to_server(servicer, server)

    # Enable gRPC reflection for debugging
    SERVICE_NAMES = (
        auction_pb2.DESCRIPTOR.services_by_name["AuctionService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    # Start server
    server.add_insecure_port(f"[::]:{SERVER_PORT}")
    server.start()

    logger.info(f"[READY] gRPC server listening on port {SERVER_PORT}")
    logger.info(f"[READY] ThreadPoolExecutor workers: {MAX_WORKERS}")
    logger.info(f"[READY] Waiting for RPC requests...")
    logger.info("")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("[SHUTDOWN] Shutting down server...")
        server.stop(grace=5)
        logger.info("[SHUTDOWN] Server stopped.")


if __name__ == "__main__":
    serve()
