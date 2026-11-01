import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import AuctionCard from '../components/AuctionCard';
import Toast from '../components/Toast';

export default function SellerDashboard() {
  const [auctions, setAuctions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);

  const fetchAuctions = async () => {
    try {
      setLoading(true);
      const result = await api.getSellerAuctions();
      if (result.success) {
        setAuctions(result.auctions);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuctions();
    const interval = setInterval(fetchAuctions, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleClose = async (auctionId) => {
    try {
      const result = await api.closeAuction(auctionId);
      if (result.success) {
        setToast({ message: `Auction closed! Winner: ${result.winner_username || 'No bids'}, Final: $${result.final_price?.toFixed(2)}`, type: 'success' });
        fetchAuctions();
      } else {
        setToast({ message: result.message, type: 'error' });
      }
    } catch (err) {
      setToast({ message: 'Failed to close auction', type: 'error' });
    }
  };

  const activeAuctions = auctions.filter(a => a.status === 'active');
  const closedAuctions = auctions.filter(a => a.status === 'closed');

  return (
    <div className="dashboard">
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}

      <div className="dashboard-header">
        <div>
          <h1>Seller Dashboard</h1>
          <p>Manage your auctions</p>
        </div>
        <div className="dashboard-actions">
          <Link to="/seller/create" className="btn btn-primary">
            + Create Auction
          </Link>
        </div>
      </div>

      <div className="dashboard-stats-row">
        <div className="stat-card">
          <span className="stat-card-value">{auctions.length}</span>
          <span className="stat-card-label">Total Auctions</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">{activeAuctions.length}</span>
          <span className="stat-card-label">Active</span>
        </div>
        <div className="stat-card">
          <span className="stat-card-value">{closedAuctions.length}</span>
          <span className="stat-card-label">Closed</span>
        </div>
      </div>

      {loading && auctions.length === 0 ? (
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading your auctions...</p>
        </div>
      ) : auctions.length === 0 ? (
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
            <path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/>
          </svg>
          <h3>No auctions yet</h3>
          <p>Create your first auction to get started</p>
          <Link to="/seller/create" className="btn btn-primary">Create Auction</Link>
        </div>
      ) : (
        <>
          {activeAuctions.length > 0 && (
            <section>
              <h2 className="section-title">Active Auctions</h2>
              <div className="auction-grid">
                {activeAuctions.map(auction => (
                  <AuctionCard
                    key={auction.auction_id}
                    auction={auction}
                    showActions
                    onClose={handleClose}
                  />
                ))}
              </div>
            </section>
          )}

          {closedAuctions.length > 0 && (
            <section>
              <h2 className="section-title">Closed Auctions</h2>
              <div className="auction-grid">
                {closedAuctions.map(auction => (
                  <AuctionCard key={auction.auction_id} auction={auction} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
