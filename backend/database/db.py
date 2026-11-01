"""
Database module for the Online Auction System.
Uses SQLite for persistent storage with thread-safe access.
"""

import sqlite3
import threading
import time
import uuid
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auction.db")


class Database:
    """Thread-safe SQLite database wrapper for the auction system."""

    _local = threading.local()

    def __init__(self):
        self._init_db()

    def _get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(DB_PATH)
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
        return self._local.connection

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('buyer', 'seller')),
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS auctions (
                auction_id TEXT PRIMARY KEY,
                item_name TEXT NOT NULL,
                description TEXT,
                starting_price REAL NOT NULL,
                current_highest_bid REAL NOT NULL DEFAULT 0,
                highest_bidder_id TEXT,
                highest_bidder_username TEXT DEFAULT '',
                seller_id TEXT NOT NULL,
                seller_username TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'closed')),
                end_time INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                total_bids INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (seller_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS bids (
                bid_id TEXT PRIMARY KEY,
                auction_id TEXT NOT NULL,
                bidder_id TEXT NOT NULL,
                bidder_username TEXT NOT NULL,
                bid_amount REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                thread_id TEXT,
                FOREIGN KEY (auction_id) REFERENCES auctions(auction_id),
                FOREIGN KEY (bidder_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_auctions_status ON auctions(status);
            CREATE INDEX IF NOT EXISTS idx_bids_auction ON bids(auction_id);
            CREATE INDEX IF NOT EXISTS idx_bids_bidder ON bids(bidder_id);

            INSERT OR IGNORE INTO users (user_id, username, password_hash, role, created_at)
            VALUES ('demo-seller', 'DemoSeller', 'demo', 'seller', 0);

            INSERT OR IGNORE INTO users (user_id, username, password_hash, role, created_at)
            VALUES ('demo-bidder', 'DemoBidder', 'demo', 'buyer', 0);
        """)
        conn.commit()

    # ─── User Operations ──────────────────────────────────────────────────

    def create_user(self, username, password, role):
        """Register a new user. Returns (success, message, user_id)."""
        conn = self._get_connection()
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        try:
            conn.execute(
                "INSERT INTO users (user_id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, password_hash, role, int(time.time())),
            )
            conn.commit()
            return True, "User registered successfully", user_id
        except sqlite3.IntegrityError:
            return False, "Username already exists", ""

    def authenticate_user(self, username, password):
        """Authenticate a user. Returns (success, message, token, user_id, role, username)."""
        conn = self._get_connection()
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        row = conn.execute(
            "SELECT user_id, role, username FROM users WHERE username = ? AND password_hash = ?",
            (username, password_hash),
        ).fetchone()

        if row:
            token = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO tokens (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, row["user_id"], int(time.time())),
            )
            conn.commit()
            return True, "Login successful", token, row["user_id"], row["role"], row["username"]
        return False, "Invalid credentials", "", "", "", ""

    def validate_token(self, token):
        """Validate a token. Returns (user_id, username, role) or None."""
        conn = self._get_connection()
        row = conn.execute(
            """SELECT t.user_id, u.username, u.role 
               FROM tokens t JOIN users u ON t.user_id = u.user_id 
               WHERE t.token = ?""",
            (token,),
        ).fetchone()

        if row:
            return row["user_id"], row["username"], row["role"]
        return None

    # ─── Auction Operations ───────────────────────────────────────────────

    def create_auction(self, seller_id, seller_username, item_name, description, starting_price, duration_seconds):
        """Create a new auction. Returns (success, message, auction_id)."""
        conn = self._get_connection()
        auction_id = str(uuid.uuid4())
        now = int(time.time())
        end_time = now + duration_seconds

        try:
            conn.execute(
                """INSERT INTO auctions 
                   (auction_id, item_name, description, starting_price, current_highest_bid,
                    seller_id, seller_username, status, end_time, created_at, total_bids)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 0)""",
                (auction_id, item_name, description, starting_price, starting_price,
                 seller_id, seller_username, end_time, now),
            )
            conn.commit()
            return True, "Auction created successfully", auction_id
        except Exception as e:
            return False, str(e), ""

    def get_active_auctions(self, search_query=""):
        """Get all active auctions, optionally filtered by search query."""
        conn = self._get_connection()
        now = int(time.time())

        # Auto-close expired auctions
        conn.execute(
            "UPDATE auctions SET status = 'closed' WHERE status = 'active' AND end_time <= ?",
            (now,),
        )
        conn.commit()

        if search_query:
            rows = conn.execute(
                """SELECT * FROM auctions WHERE status = 'active' 
                   AND (item_name LIKE ? OR description LIKE ?)
                   ORDER BY created_at DESC""",
                (f"%{search_query}%", f"%{search_query}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM auctions WHERE status = 'active' ORDER BY created_at DESC"
            ).fetchall()

        return [dict(row) for row in rows]

    def get_auction(self, auction_id):
        """Get a single auction by ID."""
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM auctions WHERE auction_id = ?", (auction_id,)).fetchone()
        return dict(row) if row else None

    def get_seller_auctions(self, seller_id):
        """Get all auctions created by a seller."""
        conn = self._get_connection()
        now = int(time.time())

        # Auto-close expired auctions
        conn.execute(
            "UPDATE auctions SET status = 'closed' WHERE status = 'active' AND end_time <= ?",
            (now,),
        )
        conn.commit()

        rows = conn.execute(
            "SELECT * FROM auctions WHERE seller_id = ? ORDER BY created_at DESC",
            (seller_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_auction_bid(self, auction_id, bid_amount, bidder_id, bidder_username, thread_id):
        """
        Update auction with new bid. Returns (success, message, bid_id).
        NOTE: This does NOT do validation — the caller must hold the auction lock
        and validate before calling this.
        """
        conn = self._get_connection()
        bid_id = str(uuid.uuid4())
        now = int(time.time())

        try:
            conn.execute(
                """UPDATE auctions 
                   SET current_highest_bid = ?, highest_bidder_id = ?, 
                       highest_bidder_username = ?, total_bids = total_bids + 1
                   WHERE auction_id = ?""",
                (bid_amount, bidder_id, bidder_username, auction_id),
            )
            conn.execute(
                """INSERT INTO bids (bid_id, auction_id, bidder_id, bidder_username, bid_amount, timestamp, thread_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (bid_id, auction_id, bidder_id, bidder_username, bid_amount, now, thread_id),
            )
            conn.commit()
            return True, "Bid placed successfully", bid_id
        except Exception as e:
            return False, str(e), ""

    def get_bid_history(self, auction_id):
        """Get all bids for an auction, ordered by timestamp descending."""
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT b.*, a.item_name FROM bids b 
               JOIN auctions a ON b.auction_id = a.auction_id
               WHERE b.auction_id = ? ORDER BY b.timestamp DESC""",
            (auction_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_user_bids(self, user_id):
        """Get all bids placed by a user."""
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT b.*, a.item_name FROM bids b
               JOIN auctions a ON b.auction_id = a.auction_id
               WHERE b.bidder_id = ? ORDER BY b.timestamp DESC""",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close_auction(self, auction_id):
        """Close an auction. Returns (success, message, final_price, winner_username)."""
        conn = self._get_connection()
        auction = self.get_auction(auction_id)
        if not auction:
            return False, "Auction not found", 0, ""
        if auction["status"] == "closed":
            return False, "Auction already closed", 0, ""

        conn.execute(
            "UPDATE auctions SET status = 'closed' WHERE auction_id = ?",
            (auction_id,),
        )
        conn.commit()

        winner = auction.get("highest_bidder_username", "No bids")
        final_price = auction["current_highest_bid"]
        return True, "Auction closed successfully", final_price, winner

    # ─── Demo Operations ──────────────────────────────────────────────────

    def create_demo_auction(self, starting_price=100.0):
        """Create a demo auction for race condition testing."""
        conn = self._get_connection()
        auction_id = "demo-" + str(uuid.uuid4())[:8]
        now = int(time.time())

        conn.execute(
            """INSERT INTO auctions 
               (auction_id, item_name, description, starting_price, current_highest_bid,
                seller_id, seller_username, status, end_time, created_at, total_bids)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 0)""",
            (auction_id, "Demo Item", "Race condition demo item", starting_price, starting_price,
             "demo-seller", "DemoSeller", now + 3600, now),
        )
        conn.commit()
        return auction_id

    def update_demo_bid_unsafe(self, auction_id, bid_amount, bidder_name, thread_id):
        """Unsafe bid update for race condition demo (no locks)."""
        conn = self._get_connection()
        bid_id = str(uuid.uuid4())
        now = int(time.time())

        conn.execute(
            """UPDATE auctions SET current_highest_bid = ?, highest_bidder_username = ?,
                      total_bids = total_bids + 1 WHERE auction_id = ?""",
            (bid_amount, bidder_name, auction_id),
        )
        conn.execute(
            """INSERT INTO bids (bid_id, auction_id, bidder_id, bidder_username, bid_amount, timestamp, thread_id)
               VALUES (?, ?, 'demo-bidder', ?, ?, ?, ?)""",
            (bid_id, auction_id, bidder_name, bid_amount, now, thread_id),
        )
        conn.commit()

    def delete_demo_auction(self, auction_id):
        """Clean up a demo auction."""
        conn = self._get_connection()
        conn.execute("DELETE FROM bids WHERE auction_id = ?", (auction_id,))
        conn.execute("DELETE FROM auctions WHERE auction_id = ?", (auction_id,))
        conn.commit()
