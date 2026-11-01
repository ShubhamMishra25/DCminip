import { useState } from 'react';
import { useAuctions } from '../hooks/useAuctions';
import AuctionCard from '../components/AuctionCard';

export default function BuyerDashboard() {
  const [search, setSearch] = useState('');
  const { auctions, loading, error, refetch } = useAuctions();

  const handleSearch = (e) => {
    e.preventDefault();
    refetch(search);
  };

  const filteredAuctions = search
    ? auctions.filter(a =>
        a.item_name.toLowerCase().includes(search.toLowerCase()) ||
        a.description?.toLowerCase().includes(search.toLowerCase())
      )
    : auctions;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h1>Active Auctions</h1>
          <p>Browse and bid on live auctions</p>
        </div>
        <div className="dashboard-stats">
          <div className="mini-stat">
            <span className="mini-stat-value">{auctions.length}</span>
            <span className="mini-stat-label">Active</span>
          </div>
        </div>
      </div>

      <form onSubmit={handleSearch} className="search-bar">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8"/>
          <path d="M21 21l-4.35-4.35"/>
        </svg>
        <input
          type="text"
          placeholder="Search auctions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="submit" className="btn btn-primary btn-sm">Search</button>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {loading && auctions.length === 0 ? (
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading auctions...</p>
        </div>
      ) : filteredAuctions.length === 0 ? (
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          <h3>No auctions found</h3>
          <p>Check back later for new listings</p>
        </div>
      ) : (
        <div className="auction-grid">
          {filteredAuctions.map(auction => (
            <AuctionCard key={auction.auction_id} auction={auction} />
          ))}
        </div>
      )}
    </div>
  );
}
