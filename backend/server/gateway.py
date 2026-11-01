"""
HTTP/JSON Gateway for the gRPC Auction Server.

This thin HTTP layer translates browser HTTP requests into gRPC calls.
All actual business logic runs through the gRPC service implementation.
This is an alternative to Envoy + grpc-web for simpler deployment.

Key Improvements:
- Persistent thread-safe gRPC channel reuse (no TCP churn)
- Immediate stream.cancel() on SSE client disconnect
- Graceful connection reset/abort handling
- Higher default timeouts to prevent false DEADLINE_EXCEEDED errors
"""

import sys
import os
import json
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import grpc
from generated import auction_pb2, auction_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gateway")

GRPC_SERVER = "localhost:50051"
GATEWAY_PORT = 8000

# Persistent thread-safe gRPC channel and stub
_channel = None
_stub = None
_channel_lock = threading.Lock()


def get_grpc_stub():
    """Get or initialize the shared gRPC stub."""
    global _channel, _stub
    if _stub is None:
        with _channel_lock:
            if _stub is None:
                _channel = grpc.insecure_channel(
                    GRPC_SERVER,
                    options=[
                        ("grpc.max_send_message_length", 50 * 1024 * 1024),
                        ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                        ("grpc.keepalive_time_ms", 30000),
                        ("grpc.keepalive_timeout_ms", 10000),
                        ("grpc.http2.max_pings_without_data", 0),
                    ],
                )
                _stub = auction_pb2_grpc.AuctionServiceStub(_channel)
    return _stub


class GatewayHandler(BaseHTTPRequestHandler):
    """HTTP request handler that proxies to gRPC."""

    def log_message(self, format, *args):
        logger.info(f"[HTTP] {self.client_address[0]} - {format % args}")

    def _send_json(self, data, status=200):
        """Send a JSON response safely."""
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _get_token(self):
        """Extract token from Authorization header."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return ""

    def _read_body(self):
        """Read and parse JSON request body."""
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        try:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Max-Age", "86400")
            self.end_headers()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            stub = get_grpc_stub()

            if path == "/api/auctions":
                token = self._get_token()
                search = query.get("search", [""])[0]
                resp = stub.GetActiveAuctions(
                    auction_pb2.GetActiveAuctionsRequest(token=token, search_query=search),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "auctions": [self._auction_to_dict(a) for a in resp.auctions],
                })

            elif path.startswith("/api/auctions/") and path.endswith("/highest-bid"):
                auction_id = path.split("/")[3]
                token = self._get_token()
                resp = stub.GetHighestBid(
                    auction_pb2.GetHighestBidRequest(token=token, auction_id=auction_id),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "highest_bid": resp.highest_bid,
                    "highest_bidder": resp.highest_bidder,
                    "auction_id": resp.auction_id,
                })

            elif path.startswith("/api/auctions/") and path.endswith("/bids"):
                auction_id = path.split("/")[3]
                token = self._get_token()
                resp = stub.GetBidHistory(
                    auction_pb2.GetBidHistoryRequest(token=token, auction_id=auction_id),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "bids": [self._bid_to_dict(b) for b in resp.bids],
                })

            elif path.startswith("/api/auctions/") and path.endswith("/stream"):
                # Server-Sent Events for real-time bid updates
                auction_id = path.split("/")[3]
                token = query.get("token", [""])[0]
                self._handle_sse(stub, auction_id, token)
                return

            elif path.startswith("/api/auctions/"):
                auction_id = path.split("/")[3]
                token = self._get_token()
                resp = stub.GetAuctionDetail(
                    auction_pb2.GetAuctionDetailRequest(token=token, auction_id=auction_id),
                    timeout=20,
                )
                if resp.success:
                    self._send_json({
                        "success": True,
                        "auction": self._auction_to_dict(resp.auction),
                    })
                else:
                    self._send_json({"success": False, "message": resp.message}, 404)

            elif path == "/api/seller/auctions":
                token = self._get_token()
                resp = stub.GetSellerAuctions(
                    auction_pb2.GetSellerAuctionsRequest(token=token),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "auctions": [self._auction_to_dict(a) for a in resp.auctions],
                })

            elif path == "/api/user/bids":
                token = self._get_token()
                resp = stub.GetUserBids(
                    auction_pb2.GetUserBidsRequest(token=token),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "bids": [self._bid_to_dict(b) for b in resp.bids],
                })

            else:
                self._send_json({"error": "Not found"}, 404)

        except grpc.RpcError as e:
            logger.error(f"gRPC error: {e.code()} - {e.details()}")
            self._send_json({"success": False, "message": f"Server error: {e.details()}"}, 500)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as e:
            logger.error(f"Gateway error: {e}")
            self._send_json({"success": False, "message": str(e)}, 500)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        try:
            stub = get_grpc_stub()

            if path == "/api/register":
                resp = stub.RegisterUser(
                    auction_pb2.RegisterRequest(
                        username=body.get("username", ""),
                        password=body.get("password", ""),
                        role=body.get("role", "buyer"),
                    ),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "message": resp.message,
                    "user_id": resp.user_id,
                })

            elif path == "/api/login":
                resp = stub.Login(
                    auction_pb2.LoginRequest(
                        username=body.get("username", ""),
                        password=body.get("password", ""),
                    ),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "message": resp.message,
                    "token": resp.token,
                    "user_id": resp.user_id,
                    "role": resp.role,
                    "username": resp.username,
                })

            elif path == "/api/auctions" and self.command == "POST":
                token = self._get_token()
                resp = stub.CreateAuction(
                    auction_pb2.CreateAuctionRequest(
                        token=token,
                        item_name=body.get("item_name", ""),
                        description=body.get("description", ""),
                        starting_price=float(body.get("starting_price", 0)),
                        duration_seconds=int(body.get("duration_seconds", 300)),
                    ),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "message": resp.message,
                    "auction_id": resp.auction_id,
                })

            elif path == "/api/bids":
                token = self._get_token()
                resp = stub.PlaceBid(
                    auction_pb2.PlaceBidRequest(
                        token=token,
                        auction_id=body.get("auction_id", ""),
                        bid_amount=float(body.get("bid_amount", 0)),
                    ),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "message": resp.message,
                    "current_highest_bid": resp.current_highest_bid,
                    "highest_bidder": resp.highest_bidder,
                    "thread_id": resp.thread_id,
                    "timestamp": resp.timestamp,
                })

            elif path.startswith("/api/auctions/") and path.endswith("/close"):
                auction_id = path.split("/")[3]
                token = self._get_token()
                resp = stub.CloseAuction(
                    auction_pb2.CloseAuctionRequest(token=token, auction_id=auction_id),
                    timeout=20,
                )
                self._send_json({
                    "success": resp.success,
                    "message": resp.message,
                    "final_price": resp.final_price,
                    "winner_username": resp.winner_username,
                })

            elif path == "/api/demo/race-condition":
                resp = stub.DemoRaceCondition(
                    auction_pb2.RaceConditionRequest(
                        num_concurrent_bids=int(body.get("num_concurrent_bids", 10)),
                        use_locks=bool(body.get("use_locks", False)),
                    ),
                    timeout=60,
                )
                self._send_json({
                    "success": resp.success,
                    "report": resp.report,
                    "expected_highest_bid": resp.expected_highest_bid,
                    "actual_highest_bid": resp.actual_highest_bid,
                    "race_condition_detected": resp.race_condition_detected,
                    "logs": list(resp.logs),
                })

            else:
                self._send_json({"error": "Not found"}, 404)

        except grpc.RpcError as e:
            logger.error(f"gRPC error: {e.code()} - {e.details()}")
            self._send_json({"success": False, "message": f"Server error: {e.details()}"}, 500)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as e:
            logger.error(f"Gateway error: {e}")
            self._send_json({"success": False, "message": str(e)}, 500)

    def _handle_sse(self, stub, auction_id, token):
        """Handle Server-Sent Events for real-time bid updates with cancellation cleanup."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return

        subscription = auction_pb2.BidUpdateSubscription(
            token=token, auction_id=auction_id
        )
        stream = stub.SubscribeToBidUpdates(subscription)
        try:
            for update in stream:
                data = json.dumps({
                    "auction_id": update.auction_id,
                    "new_highest_bid": update.new_highest_bid,
                    "highest_bidder": update.highest_bidder,
                    "timestamp": update.timestamp,
                    "total_bids": update.total_bids,
                    "bidder_username": update.bidder_username,
                })
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            logger.info(f"[GATEWAY] Client disconnected SSE stream for auction {auction_id}")
        except Exception as e:
            logger.error(f"[GATEWAY] SSE stream error: {e}")
        finally:
            stream.cancel()

    def _auction_to_dict(self, auction):
        """Convert protobuf AuctionItem to dict."""
        return {
            "auction_id": auction.auction_id,
            "item_name": auction.item_name,
            "description": auction.description,
            "starting_price": auction.starting_price,
            "current_highest_bid": auction.current_highest_bid,
            "highest_bidder": auction.highest_bidder,
            "seller_id": auction.seller_id,
            "seller_username": auction.seller_username,
            "status": auction.status,
            "end_time": auction.end_time,
            "created_at": auction.created_at,
            "total_bids": auction.total_bids,
        }

    def _bid_to_dict(self, bid):
        """Convert protobuf BidRecord to dict."""
        return {
            "bid_id": bid.bid_id,
            "auction_id": bid.auction_id,
            "bidder_id": bid.bidder_id,
            "bidder_username": bid.bidder_username,
            "bid_amount": bid.bid_amount,
            "timestamp": bid.timestamp,
            "thread_id": bid.thread_id,
            "item_name": bid.item_name,
        }


class ThreadedHTTPServer(HTTPServer):
    """HTTP server that handles each request in a new thread."""
    def process_request(self, request, client_address):
        thread = threading.Thread(target=self._handle_request_thread, args=(request, client_address))
        thread.daemon = True
        thread.start()

    def _handle_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def start_gateway():
    """Start the HTTP gateway server."""
    server = ThreadedHTTPServer(("0.0.0.0", GATEWAY_PORT), GatewayHandler)
    logger.info(f"[GATEWAY] HTTP gateway listening on port {GATEWAY_PORT}")
    logger.info(f"[GATEWAY] Proxying to gRPC server at {GRPC_SERVER}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[GATEWAY] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    start_gateway()
