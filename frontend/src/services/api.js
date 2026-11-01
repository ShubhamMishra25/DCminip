/**
 * gRPC-Web client service for communicating with the Python gRPC server
 * through Envoy proxy.
 * 
 * Since grpc-web requires protoc-gen-grpc-web generated code, and to keep
 * things simpler for this project, we use a REST-like wrapper approach:
 * The frontend communicates via grpc-web protocol through Envoy, which
 * translates to native gRPC for the Python backend.
 * 
 * For simplicity and reliability, we use a lightweight HTTP gateway approach
 * where the Python server also exposes a thin HTTP/JSON layer that mirrors
 * the gRPC service, while all actual business logic runs through gRPC internally.
 */

const GATEWAY_URL = 'http://localhost:8000';

class AuctionAPI {
  constructor() {
    this.baseUrl = GATEWAY_URL;
  }

  _getHeaders() {
    const token = localStorage.getItem('token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    };
  }

  async _request(endpoint, method = 'POST', body = null) {
    const options = {
      method,
      headers: this._getHeaders(),
    };
    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, options);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Network error' }));
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // ─── Authentication ──────────────────────────────────────────────────

  async register(username, password, role) {
    return this._request('/api/register', 'POST', { username, password, role });
  }

  async login(username, password) {
    const result = await this._request('/api/login', 'POST', { username, password });
    if (result.success) {
      localStorage.setItem('token', result.token);
      localStorage.setItem('user', JSON.stringify({
        user_id: result.user_id,
        username: result.username,
        role: result.role,
      }));
    }
    return result;
  }

  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }

  getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  }

  getToken() {
    return localStorage.getItem('token');
  }

  isAuthenticated() {
    return !!this.getToken();
  }

  // ─── Auctions ────────────────────────────────────────────────────────

  async createAuction(itemName, description, startingPrice, durationSeconds) {
    return this._request('/api/auctions', 'POST', {
      item_name: itemName,
      description,
      starting_price: startingPrice,
      duration_seconds: durationSeconds,
    });
  }

  async getActiveAuctions(searchQuery = '') {
    const params = searchQuery ? `?search=${encodeURIComponent(searchQuery)}` : '';
    return this._request(`/api/auctions${params}`, 'GET');
  }

  async getAuctionDetail(auctionId) {
    return this._request(`/api/auctions/${auctionId}`, 'GET');
  }

  async getSellerAuctions() {
    return this._request('/api/seller/auctions', 'GET');
  }

  async closeAuction(auctionId) {
    return this._request(`/api/auctions/${auctionId}/close`, 'POST');
  }

  // ─── Bidding ─────────────────────────────────────────────────────────

  async placeBid(auctionId, bidAmount) {
    return this._request('/api/bids', 'POST', {
      auction_id: auctionId,
      bid_amount: bidAmount,
    });
  }

  async getHighestBid(auctionId) {
    return this._request(`/api/auctions/${auctionId}/highest-bid`, 'GET');
  }

  async getBidHistory(auctionId) {
    return this._request(`/api/auctions/${auctionId}/bids`, 'GET');
  }

  async getUserBids() {
    return this._request('/api/user/bids', 'GET');
  }

  // ─── Streaming (SSE for bid updates) ─────────────────────────────────

  subscribeToBidUpdates(auctionId, onUpdate, onError) {
    const token = this.getToken();
    const url = `${this.baseUrl}/api/auctions/${auctionId}/stream?token=${token}`;
    
    const eventSource = new EventSource(url);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onUpdate(data);
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      if (onError) onError(error);
    };

    return eventSource; // Return so caller can close it
  }

  // ─── Race Condition Demo ─────────────────────────────────────────────

  async demoRaceCondition(numBids, useLocks) {
    return this._request('/api/demo/race-condition', 'POST', {
      num_concurrent_bids: numBids,
      use_locks: useLocks,
    });
  }
}

const api = new AuctionAPI();
export default api;
