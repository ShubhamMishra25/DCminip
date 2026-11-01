"""
Authentication service for the Online Auction System.
Handles user registration, login, and token validation.
"""

import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Manages user authentication operations."""

    def __init__(self, db):
        self.db = db

    def register(self, username, password, role):
        """
        Register a new user.
        Returns: (success, message, user_id)
        """
        if not username or not password:
            return False, "Username and password are required", ""

        if role not in ("buyer", "seller"):
            return False, "Role must be 'buyer' or 'seller'", ""

        if len(username) < 3:
            return False, "Username must be at least 3 characters", ""

        if len(password) < 4:
            return False, "Password must be at least 4 characters", ""

        success, message, user_id = self.db.create_user(username, password, role)
        if success:
            logger.info(f"[AUTH] User registered: {username} (role={role}, id={user_id})")
        else:
            logger.warning(f"[AUTH] Registration failed for {username}: {message}")

        return success, message, user_id

    def login(self, username, password):
        """
        Authenticate a user and return a session token.
        Returns: (success, message, token, user_id, role, username)
        """
        if not username or not password:
            return False, "Username and password are required", "", "", "", ""

        success, message, token, user_id, role, uname = self.db.authenticate_user(username, password)
        if success:
            logger.info(f"[AUTH] User logged in: {uname} (role={role})")
        else:
            logger.warning(f"[AUTH] Login failed for {username}")

        return success, message, token, user_id, role, uname

    def validate_token(self, token):
        """
        Validate a session token.
        Returns: (user_id, username, role) or None
        """
        if not token:
            return None
        return self.db.validate_token(token)
