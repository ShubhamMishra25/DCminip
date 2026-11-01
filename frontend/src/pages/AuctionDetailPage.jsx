import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAuctionDetail, useBidHistory, useBidUpdates } from '../hooks/useAuctions';
import api from '../services/api';
import Toast from '../components/Toast';

export default function AuctionDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { auction, loading: loadingAuction, error, refetch: refetchAuction } = useAuctionDetail(id);
  const { bids, loading: loadingBids, refetch: refetchBids } = useBidHistory(id);

  const [bidAmount, setBidAmount] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [lastRpcMeta, setLastRpcMeta] = useState(null);

  // Real-time server streaming updates
  useBidUpdates(id, (update) => {
    refetchAuction();
    refetchBids();
    setToast({
      message: `⚡ Live Update: New highest bid $${update.new_highest_bid.toFixed(2)} by ${update.bidder_username}!`,
      type: 'info'
    });
  });

  const handlePlaceBid = async (e) => {
    e.preventDefault();
    if (!bidAmount || isNaN(bidAmount)) return;

    setSubmitting(true);
    try {
      const parsedAmount = parseFloat(bidAmount);
      const res = await api.placeBid(id, parsedAmount);

      if (res.success) {
        setToast({
          message: `Bid placed successfully! Thread: ${res.thread_id || 'Worker'}`,
          type: 'success',
        });
        setLastRpcMeta({
          threadId: res.thread_id,
          timestamp: res.timestamp,
          highestBid: res.current_highest_bid,
        });
        setBidAmount('');
        refetchAuction();
        refetchBids();
      } else {
        setToast({
          message: res.message || 'Bid rejected by server',
          type: 'error',
        });
      }
    } catch (err) {
      setToast({
        message: err.message || 'Failed to place bid (gRPC communication error)',
        type: 'error',
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingAuction && !auction) {
    return (
      <div className="flex-center py-20">
        <div className="loading-spinner"></div>
        <p className="ml-3 text-slate-400">Loading auction details...</p>
      </div>
    );
  }

  if (error || !auction) {
    return (
      <div className="max-w-3xl mx-auto py-12 px-4 text-center">
        <div className="error-banner mb-6">{error || 'Auction not found'}</div>
        <Link to="/buyer" className="btn btn-primary">
          Back to Auctions
        </Link>
      </div>
    );
  }

  const isActive = auction.status === 'active';
  const minNextBid = (auction.current_highest_bid > 0 ? auction.current_highest_bid + 1 : auction.starting_price).toFixed(2);
  const isSeller = user?.user_id === auction.seller_id;

  return (
    <div className="auction-detail-container">
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}

      <div className="breadcrumb mb-6">
        <Link to={user?.role === 'seller' ? '/seller' : '/buyer'} className="text-indigo-400 hover:underline">
          &larr; Back to Dashboard
        </Link>
      </div>

      <div className="auction-detail-grid">
        {/* Left Column: Item Information & Bid Action */}
        <div className="auction-main-card">
          <div className="flex-between mb-4">
            <span className={`status-badge ${isActive ? 'active' : 'closed'}`}>
              {isActive ? '● Live Auction' : 'Ended'}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ID: {auction.auction_id?.slice(0, 8)}...
            </span>
          </div>

          <h1 className="text-3xl font-bold text-white mb-2">{auction.item_name}</h1>
          <p className="text-slate-400 text-sm mb-6">
            Listed by <span className="text-indigo-300 font-semibold">{auction.seller_username}</span>
          </p>

          <div className="detail-description-box mb-6">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Item Description</h4>
            <p className="text-slate-200 leading-relaxed">
              {auction.description || 'No description provided by the seller.'}
            </p>
          </div>

          {/* Pricing Banner */}
          <div className="pricing-hero-card mb-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-xs text-slate-400 font-medium">Starting Price</span>
                <p className="text-xl font-bold text-slate-200">${auction.starting_price?.toFixed(2)}</p>
              </div>
              <div>
                <span className="text-xs text-indigo-300 font-medium">Current Highest Bid</span>
                <p className="text-3xl font-extrabold text-emerald-400">
                  ${auction.current_highest_bid?.toFixed(2)}
                </p>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-700/50 flex-between text-xs text-slate-300">
              <span>Leading Bidder: <strong className="text-white">{auction.highest_bidder || 'No bids yet'}</strong></span>
              <span>Total Bids: <strong className="text-white">{auction.total_bids}</strong></span>
            </div>
          </div>

          {/* Bid Placement Form */}
          {isActive ? (
            isSeller ? (
              <div className="info-box">
                <span className="info-icon">ℹ</span>
                <span>You are the seller of this auction. Sellers cannot bid on their own items.</span>
              </div>
            ) : (
              <form onSubmit={handlePlaceBid} className="bid-submission-box">
                <h3 className="text-lg font-semibold text-white mb-2">Place Your Bid</h3>
                <p className="text-xs text-slate-400 mb-4">
                  Must be higher than current highest bid (Minimum: <strong>${minNextBid}</strong>).
                  Execution is guarded with atomicity and mutex locks.
                </p>

                <div className="flex gap-3">
                  <div className="relative flex-1">
                    <span className="currency-prefix">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min={minNextBid}
                      value={bidAmount}
                      onChange={(e) => setBidAmount(e.target.value)}
                      placeholder={minNextBid}
                      required
                      className="bid-input"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="btn btn-primary px-8"
                  >
                    {submitting ? 'Verifying Lock...' : 'Submit Bid'}
                  </button>
                </div>
              </form>
            )
          ) : (
            <div className="auction-closed-banner">
              <span className="closed-icon">🔒</span>
              <div>
                <h4 className="font-bold text-slate-200">This Auction Has Closed</h4>
                <p className="text-xs text-slate-400">
                  Winner: <strong className="text-emerald-400">{auction.highest_bidder || 'None'}</strong> with final bid of <strong>${auction.current_highest_bid?.toFixed(2)}</strong>
                </p>
              </div>
            </div>
          )}

          {/* Distributed Computing Metadata telemetry */}
          {lastRpcMeta && (
            <div className="rpc-telemetry-badge mt-6">
              <span className="telemetry-title">⚡ Distributed RPC Telemetry:</span>
              <span>Worker Thread ID: <code>{lastRpcMeta.threadId}</code></span>
              <span>Timestamp: <code>{lastRpcMeta.timestamp}</code></span>
            </div>
          )}
        </div>

        {/* Right Column: Real-time Bid History & Sync Log */}
        <div className="auction-sidebar-card">
          <div className="flex-between mb-4 border-b border-slate-700/60 pb-3">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <span className="stream-indicator"></span>
              Live Bid History
            </h3>
            <span className="text-xs text-slate-400">{bids.length} records</span>
          </div>

          <div className="bids-history-list">
            {loadingBids && bids.length === 0 ? (
              <p className="text-sm text-slate-400 py-8 text-center">Loading bids...</p>
            ) : bids.length === 0 ? (
              <div className="empty-history-text py-12 text-center text-slate-500">
                <p>No bids have been placed yet.</p>
                <p className="text-xs mt-1">Be the first bidder!</p>
              </div>
            ) : (
              bids.map((bid, index) => (
                <div
                  key={bid.bid_id || index}
                  className={`bid-history-item ${index === 0 ? 'top-bid' : ''}`}
                >
                  <div className="flex-between">
                    <span className="bidder-name font-semibold text-slate-200">
                      {bid.bidder_username}
                      {index === 0 && <span className="leader-tag ml-2">Highest</span>}
                    </span>
                    <span className="bid-val text-emerald-400 font-bold">
                      ${bid.bid_amount?.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex-between text-[11px] text-slate-400 mt-1 font-mono">
                    <span>
                      {bid.timestamp ? new Date(bid.timestamp * 1000).toLocaleTimeString() : 'Just now'}
                    </span>
                    {bid.thread_id && (
                      <span title="Server Thread ID that processed this bid">
                        Thread: {bid.thread_id}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
