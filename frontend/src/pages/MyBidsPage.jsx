import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

export default function MyBidsPage() {
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchUserBids() {
      try {
        setLoading(true);
        const res = await api.getUserBids();
        if (res.success) {
          setBids(res.bids || []);
        } else {
          setError(res.message || 'Failed to load your bids');
        }
      } catch (err) {
        setError(err.message || 'Error fetching bids');
      } finally {
        setLoading(false);
      }
    }
    fetchUserBids();
  }, []);

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h1>My Bidding History</h1>
          <p>Complete history of all bids you have placed across auctions</p>
        </div>
        <div className="dashboard-stats">
          <div className="mini-stat">
            <span className="mini-stat-value">{bids.length}</span>
            <span className="mini-stat-label">Total Bids</span>
          </div>
        </div>
      </div>

      {error && <div className="error-banner mb-6">{error}</div>}

      {loading ? (
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading your bidding history...</p>
        </div>
      ) : bids.length === 0 ? (
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          <h3>No bids placed yet</h3>
          <p>Explore active auctions and place your first bid!</p>
          <Link to="/buyer" className="btn btn-primary mt-4">
            Browse Auctions
          </Link>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Auction Item</th>
                <th>Bid Amount</th>
                <th>Timestamp</th>
                <th>Processed Thread</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {bids.map((bid, i) => (
                <tr key={bid.bid_id || i}>
                  <td className="font-semibold text-white">
                    {bid.item_name || `Auction #${bid.auction_id?.slice(0, 8)}`}
                  </td>
                  <td className="text-emerald-400 font-bold">
                    ${bid.bid_amount?.toFixed(2)}
                  </td>
                  <td className="text-slate-400 text-sm">
                    {bid.timestamp ? new Date(bid.timestamp * 1000).toLocaleString() : 'N/A'}
                  </td>
                  <td className="text-slate-400 font-mono text-xs">
                    {bid.thread_id || 'Main'}
                  </td>
                  <td>
                    <Link
                      to={`/auction/${bid.auction_id}`}
                      className="btn btn-ghost btn-sm"
                    >
                      View Auction &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
