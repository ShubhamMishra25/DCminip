"""
gRPC Auction Service implementation.
Maps gRPC calls to AuctionManager operations.

Demonstrates:
- Unary RPC (Login, Register, CreateAuction, PlaceBid, etc.)
- Server Streaming RPC (SubscribeToBidUpdates)
- RPC error handling and deadlines
- Thread ID and timestamp logging
"""

import sys
import os
import time
import threading
import logging
import grpc

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from generated import auction_pb2, auction_pb2_grpc
from server.auction_manager import AuctionManager
from concurrency.race_condition_demo import RaceConditionDemo

logger = logging.getLogger(__name__)


class AuctionServiceServicer(auction_pb2_grpc.AuctionServiceServicer):
    """
    gRPC service implementation for the Online Auction System.
    Each method is a remote procedure that can be called by the client.
    """

    def __init__(self, auction_manager: AuctionManager, db):
        self.manager = auction_manager
        self.db = db
        self.race_demo = RaceConditionDemo(db)

    def _log_rpc(self, method_name, context):
        """Log RPC call with thread info."""
        thread_id = threading.current_thread().ident
        peer = context.peer() if context.peer() else "unknown"
        logger.info(
            f"[RPC] {method_name} called | Thread: {thread_id} | "
            f"Peer: {peer} | Time: {time.strftime('%H:%M:%S')}"
        )

    # ─── Unary RPCs ───────────────────────────────────────────────────────

    def RegisterUser(self, request, context):
        """Unary RPC: Register a new user."""
        self._log_rpc("RegisterUser", context)

        success, message, user_id = self.manager.auth.register(
            request.username, request.password, request.role
        )
        return auction_pb2.RegisterResponse(
            success=success, message=message, user_id=user_id
        )

    def Login(self, request, context):
        """Unary RPC: Authenticate user and return token."""
        self._log_rpc("Login", context)

        success, message, token, user_id, role, username = self.manager.auth.login(
            request.username, request.password
        )
        return auction_pb2.LoginResponse(
            success=success,
            message=message,
            token=token,
            user_id=user_id,
            role=role,
            username=username,
        )

    def CreateAuction(self, request, context):
        """Unary RPC: Create a new auction."""
        self._log_rpc("CreateAuction", context)

        success, message, auction_id = self.manager.create_auction(
            request.token,
            request.item_name,
            request.description,
            request.starting_price,
            request.duration_seconds,
        )
        if not success:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(message)
        return auction_pb2.CreateAuctionResponse(
            success=success, message=message, auction_id=auction_id
        )

    def GetActiveAuctions(self, request, context):
        """Unary RPC: Get all active auctions."""
        self._log_rpc("GetActiveAuctions", context)

        success, auctions = self.manager.get_active_auctions(
            request.token, request.search_query
        )
        if not success:
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid token")
            return auction_pb2.GetActiveAuctionsResponse(success=False)

        auction_items = [self._auction_to_proto(a) for a in auctions]
        return auction_pb2.GetActiveAuctionsResponse(
            success=True, auctions=auction_items
        )

    def GetAuctionDetail(self, request, context):
        """Unary RPC: Get details for a specific auction."""
        self._log_rpc("GetAuctionDetail", context)

        success, auction, message = self.manager.get_auction_detail(
            request.token, request.auction_id
        )
        if not success:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(message)
            return auction_pb2.GetAuctionDetailResponse(
                success=False, message=message
            )

        return auction_pb2.GetAuctionDetailResponse(
            success=True,
            auction=self._auction_to_proto(auction),
            message="OK",
        )

    def PlaceBid(self, request, context):
        """Unary RPC: Place a bid on an auction (synchronized)."""
        self._log_rpc("PlaceBid", context)

        success, message, highest_bid, highest_bidder, thread_id, timestamp = (
            self.manager.place_bid(request.token, request.auction_id, request.bid_amount)
        )
        if not success and "Invalid" in message:
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details(message)

        return auction_pb2.PlaceBidResponse(
            success=success,
            message=message,
            current_highest_bid=highest_bid,
            highest_bidder=highest_bidder,
            thread_id=thread_id,
            timestamp=timestamp,
        )

    def GetHighestBid(self, request, context):
        """Unary RPC: Get the current highest bid for an auction."""
        self._log_rpc("GetHighestBid", context)

        success, highest_bid, highest_bidder, auction_id = self.manager.get_highest_bid(
            request.token, request.auction_id
        )
        return auction_pb2.GetHighestBidResponse(
            success=success,
            highest_bid=highest_bid,
            highest_bidder=highest_bidder,
            auction_id=auction_id,
        )

    def GetBidHistory(self, request, context):
        """Unary RPC: Get bid history for an auction."""
        self._log_rpc("GetBidHistory", context)

        success, bids = self.manager.get_bid_history(request.token, request.auction_id)
        bid_records = [self._bid_to_proto(b) for b in bids]
        return auction_pb2.GetBidHistoryResponse(success=success, bids=bid_records)

    def GetUserBids(self, request, context):
        """Unary RPC: Get all bids placed by the authenticated user."""
        self._log_rpc("GetUserBids", context)

        success, bids = self.manager.get_user_bids(request.token)
        bid_records = [self._bid_to_proto(b) for b in bids]
        return auction_pb2.GetUserBidsResponse(success=success, bids=bid_records)

    def CloseAuction(self, request, context):
        """Unary RPC: Close an auction."""
        self._log_rpc("CloseAuction", context)

        success, message, final_price, winner = self.manager.close_auction(
            request.token, request.auction_id
        )
        return auction_pb2.CloseAuctionResponse(
            success=success,
            message=message,
            final_price=final_price,
            winner_username=winner,
        )

    def GetSellerAuctions(self, request, context):
        """Unary RPC: Get auctions created by the authenticated seller."""
        self._log_rpc("GetSellerAuctions", context)

        success, auctions = self.manager.get_seller_auctions(request.token)
        auction_items = [self._auction_to_proto(a) for a in auctions]
        return auction_pb2.GetSellerAuctionsResponse(
            success=True, auctions=auction_items
        )

    # ─── Server Streaming RPC ─────────────────────────────────────────────

    def SubscribeToBidUpdates(self, request, context):
        """
        Server Streaming RPC: Stream real-time bid updates to clients.
        
        The client sends a subscription request and receives a stream of
        BidUpdate messages whenever a new bid is placed on the auction.
        """
        self._log_rpc("SubscribeToBidUpdates", context)

        user = self.manager.auth.validate_token(request.token)
        if not user:
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Invalid token")
            return

        auction_id = request.auction_id
        q = self.manager.bidding.subscribe(auction_id)
        logger.info(f"[STREAM] Client subscribed to auction {auction_id}")

        stop_event = threading.Event()
        def on_rpc_done():
            stop_event.set()
        context.add_callback(on_rpc_done)

        try:
            while context.is_active() and not stop_event.is_set():
                try:
                    # Wait for updates with a short timeout to check if context is still active
                    update = q.get(timeout=0.5)
                    yield auction_pb2.BidUpdate(
                        auction_id=update["auction_id"],
                        new_highest_bid=update["new_highest_bid"],
                        highest_bidder=update["highest_bidder"],
                        timestamp=update["timestamp"],
                        total_bids=update["total_bids"],
                        bidder_username=update["bidder_username"],
                    )
                except Exception:
                    # Timeout — loop back and check context.is_active() & stop_event
                    continue
        finally:
            self.manager.bidding.unsubscribe(auction_id, q)
            logger.info(f"[STREAM] Client unsubscribed from auction {auction_id}")

    # ─── Race Condition Demo ──────────────────────────────────────────────

    def DemoRaceCondition(self, request, context):
        """
        Unary RPC: Demonstrate race conditions with/without synchronization.
        """
        self._log_rpc("DemoRaceCondition", context)

        result = self.race_demo.run_demo(
            num_concurrent_bids=request.num_concurrent_bids,
            use_locks=request.use_locks,
        )
        return auction_pb2.RaceConditionResponse(
            success=True,
            report=result["report"],
            expected_highest_bid=result["expected_highest_bid"],
            actual_highest_bid=result["actual_highest_bid"],
            race_condition_detected=result["race_condition_detected"],
            logs=result["logs"],
        )

    # ─── Helper Methods ───────────────────────────────────────────────────

    def _auction_to_proto(self, auction_dict):
        """Convert auction dict to protobuf AuctionItem."""
        return auction_pb2.AuctionItem(
            auction_id=auction_dict.get("auction_id", ""),
            item_name=auction_dict.get("item_name", ""),
            description=auction_dict.get("description", ""),
            starting_price=auction_dict.get("starting_price", 0),
            current_highest_bid=auction_dict.get("current_highest_bid", 0),
            highest_bidder=auction_dict.get("highest_bidder_username", ""),
            seller_id=auction_dict.get("seller_id", ""),
            seller_username=auction_dict.get("seller_username", ""),
            status=auction_dict.get("status", ""),
            end_time=auction_dict.get("end_time", 0),
            created_at=auction_dict.get("created_at", 0),
            total_bids=auction_dict.get("total_bids", 0),
        )

    def _bid_to_proto(self, bid_dict):
        """Convert bid dict to protobuf BidRecord."""
        return auction_pb2.BidRecord(
            bid_id=bid_dict.get("bid_id", ""),
            auction_id=bid_dict.get("auction_id", ""),
            bidder_id=bid_dict.get("bidder_id", ""),
            bidder_username=bid_dict.get("bidder_username", ""),
            bid_amount=bid_dict.get("bid_amount", 0),
            timestamp=bid_dict.get("timestamp", 0),
            thread_id=bid_dict.get("thread_id", ""),
            item_name=bid_dict.get("item_name", ""),
        )
