import { Link } from 'react-router-dom';

function formatTimeLeft(endTime) {
  const now = Math.floor(Date.now() / 1000);
  const diff = endTime - now;
  if (diff <= 0) return 'Ended';
  const hours = Math.floor(diff / 3600);
  const minutes = Math.floor((diff % 3600) / 60);
  const seconds = diff % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export default function AuctionCard({ auction, showActions = false, onClose }) {
  const isActive = auction.status === 'active';
  const timeLeft = formatTimeLeft(auction.end_time);

  return (
    <div className={`auction-card ${!isActive ? 'closed' : ''}`}>
      <div className="auction-card-header">
        <div className="auction-status-row">
          <span className={`status-badge ${isActive ? 'active' : 'closed'}`}>
            {isActive ? 'Live' : 'Closed'}
          </span>
          {isActive && (
            <span className="time-left">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 6v6l4 2"/>
              </svg>
              {timeLeft}
            </span>
          )}
        </div>
        <h3 className="auction-title">{auction.item_name}</h3>
        <p className="auction-seller">by {auction.seller_username}</p>
      </div>

      <div className="auction-card-body">
        <p className="auction-description">
          {auction.description || 'No description provided'}
        </p>

        <div className="auction-stats">
          <div className="stat">
            <span className="stat-label">Starting Price</span>
            <span className="stat-value">${auction.starting_price?.toFixed(2)}</span>
          </div>
          <div className="stat highlight">
            <span className="stat-label">Current Bid</span>
            <span className="stat-value">${auction.current_highest_bid?.toFixed(2)}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Total Bids</span>
            <span className="stat-value">{auction.total_bids}</span>
          </div>
        </div>

        {auction.highest_bidder && (
          <p className="highest-bidder">
            Highest Bidder: <strong>{auction.highest_bidder}</strong>
          </p>
        )}
      </div>

      <div className="auction-card-footer">
        <Link to={`/auction/${auction.auction_id}`} className="btn btn-primary btn-sm">
          View Details
        </Link>
        {showActions && isActive && onClose && (
          <button onClick={() => onClose(auction.auction_id)} className="btn btn-danger btn-sm">
            Close Auction
          </button>
        )}
      </div>
    </div>
  );
}
