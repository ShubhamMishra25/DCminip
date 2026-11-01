import { useState, useEffect, useCallback } from 'react';
import api from '../services/api';

export function useAuctions(autoRefresh = true) {
  const [auctions, setAuctions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAuctions = useCallback(async (search = '') => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getActiveAuctions(search);
      if (result.success) {
        setAuctions(result.auctions);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAuctions();
    if (autoRefresh) {
      // Relaxed 10-second polling for active auction listings
      const interval = setInterval(() => fetchAuctions(), 10000);
      return () => clearInterval(interval);
    }
  }, [fetchAuctions, autoRefresh]);

  return { auctions, loading, error, refetch: fetchAuctions };
}

export function useAuctionDetail(auctionId) {
  const [auction, setAuction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDetail = useCallback(async () => {
    if (!auctionId) return;
    try {
      setLoading(true);
      const result = await api.getAuctionDetail(auctionId);
      if (result.success) {
        setAuction(result.auction);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [auctionId]);

  useEffect(() => {
    fetchDetail();
    // Real-time updates handle live bids via SSE, fallback poll every 15s
    const interval = setInterval(fetchDetail, 15000);
    return () => clearInterval(interval);
  }, [fetchDetail]);

  return { auction, loading, error, refetch: fetchDetail };
}

export function useBidHistory(auctionId) {
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchBids = useCallback(async () => {
    if (!auctionId) return;
    try {
      setLoading(true);
      const result = await api.getBidHistory(auctionId);
      if (result.success) {
        setBids(result.bids);
      }
    } catch (err) {
      console.error('Failed to fetch bids:', err);
    } finally {
      setLoading(false);
    }
  }, [auctionId]);

  useEffect(() => {
    fetchBids();
    // Real-time updates handle live bids via SSE, fallback poll every 15s
    const interval = setInterval(fetchBids, 15000);
    return () => clearInterval(interval);
  }, [fetchBids]);

  return { bids, loading, refetch: fetchBids };
}

export function useBidUpdates(auctionId, onUpdate) {
  useEffect(() => {
    if (!auctionId) return;

    const eventSource = api.subscribeToBidUpdates(
      auctionId,
      (data) => {
        if (onUpdate) onUpdate(data);
      },
      (error) => {
        console.error('Bid update stream error:', error);
      }
    );

    return () => {
      eventSource.close();
    };
  }, [auctionId, onUpdate]);
}
