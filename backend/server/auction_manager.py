"""
Auction Manager – orchestrates auction operations.
Sits between the gRPC service layer and the database/services layer.
"""

import logging

logger = logging.getLogger(__name__)


class AuctionManager:
    """High-level auction operations manager."""

    def __init__(self, db, auth_service, bidding_service):
        self.db = db
        self.auth = auth_service
        self.bidding = bidding_service

    def create_auction(self, token, item_name, description, starting_price, duration_seconds):
        """Create a new auction. Only sellers can create auctions."""
        user = self.auth.validate_token(token)
        if not user:
            return False, "Invalid or expired token", ""

        user_id, username, role = user
        if role != "seller":
            return False, "Only sellers can create auctions", ""

        if not item_name:
            return False, "Item name is required", ""

        if starting_price <= 0:
            return False, "Starting price must be positive", ""

        if duration_seconds < 60:
            return False, "Duration must be at least 60 seconds", ""

        success, message, auction_id = self.db.create_auction(
            user_id, username, item_name, description, starting_price, duration_seconds
        )
        if success:
            logger.info(f"[AUCTION] Created auction {auction_id}: {item_name} by {username}")
        return success, message, auction_id

    def get_active_auctions(self, token, search_query=""):
        """Get active auctions. Any authenticated user can view."""
        user = self.auth.validate_token(token)
        if not user:
            return False, []

        auctions = self.db.get_active_auctions(search_query)
        return True, auctions

    def get_auction_detail(self, token, auction_id):
        """Get details for a specific auction."""
        user = self.auth.validate_token(token)
        if not user:
            return False, None, "Invalid token"

        auction = self.db.get_auction(auction_id)
        if not auction:
            return False, None, "Auction not found"
        return True, auction, "OK"

    def place_bid(self, token, auction_id, bid_amount):
        """Place a bid on an auction. Delegates to BiddingService for synchronization."""
        user = self.auth.validate_token(token)
        if not user:
            return False, "Invalid or expired token", 0, "", "", ""

        user_id, username, role = user
        return self.bidding.place_bid(auction_id, user_id, username, bid_amount)

    def get_highest_bid(self, token, auction_id):
        """Get the current highest bid for an auction."""
        user = self.auth.validate_token(token)
        if not user:
            return False, 0, "", auction_id

        auction = self.db.get_auction(auction_id)
        if not auction:
            return False, 0, "", auction_id
        return True, auction["current_highest_bid"], auction.get("highest_bidder_username", ""), auction_id

    def get_bid_history(self, token, auction_id):
        """Get bid history for an auction."""
        user = self.auth.validate_token(token)
        if not user:
            return False, []

        bids = self.db.get_bid_history(auction_id)
        return True, bids

    def get_user_bids(self, token):
        """Get all bids placed by the authenticated user."""
        user = self.auth.validate_token(token)
        if not user:
            return False, []

        user_id, _, _ = user
        bids = self.db.get_user_bids(user_id)
        return True, bids

    def close_auction(self, token, auction_id):
        """Close an auction. Only the seller who created it can close it."""
        user = self.auth.validate_token(token)
        if not user:
            return False, "Invalid token", 0, ""

        user_id, username, role = user
        auction = self.db.get_auction(auction_id)
        if not auction:
            return False, "Auction not found", 0, ""

        if auction["seller_id"] != user_id:
            return False, "Only the seller can close their auction", 0, ""

        return self.db.close_auction(auction_id)

    def get_seller_auctions(self, token):
        """Get all auctions created by the authenticated seller."""
        user = self.auth.validate_token(token)
        if not user:
            return False, []

        user_id, _, role = user
        if role != "seller":
            return False, []

        auctions = self.db.get_seller_auctions(user_id)
        return True, auctions
