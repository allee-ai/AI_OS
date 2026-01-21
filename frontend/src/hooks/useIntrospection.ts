/**
 * useIntrospection Hook
 * =====================
 * React hook for fetching and polling Nola's introspection state.
 * Provides real-time visibility into identity, threads, and context.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { IntrospectionData } from '../types/introspection';
import { introspectionService } from '../services/introspectionService';

interface UseIntrospectionOptions {
  /** Context level to fetch (1=minimal, 2=moderate, 3=full) */
  level?: number;
  /** Poll interval in ms (0 to disable polling) */
  pollInterval?: number;
  /** Whether to start polling immediately */
  autoStart?: boolean;
}

interface UseIntrospectionResult {
  /** Current introspection data */
  data: IntrospectionData | null;
  /** Loading state */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
  /** Manual refresh function */
  refresh: () => Promise<void>;
  /** Change context level */
  setLevel: (level: number) => void;
  /** Current context level */
  level: number;
  /** Whether polling is active */
  isPolling: boolean;
  /** Start polling */
  startPolling: () => void;
  /** Stop polling */
  stopPolling: () => void;
}

export function useIntrospection(options: UseIntrospectionOptions = {}): UseIntrospectionResult {
  const {
    level: initialLevel = 2,
    pollInterval = 5000,  // Default 5 seconds
    autoStart = true
  } = options;

  const [data, setData] = useState<IntrospectionData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(initialLevel);
  const [isPolling, setIsPolling] = useState(autoStart && pollInterval > 0);
  
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchIntrospection = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await introspectionService.getIntrospection(level);
      setData(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch introspection';
      setError(message);
      console.error('[useIntrospection] Error:', message);
    } finally {
      setIsLoading(false);
    }
  }, [level]);

  const startPolling = useCallback(() => {
    if (pollInterval <= 0) return;
    
    setIsPolling(true);
    // Clear any existing timer
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
    }
    
    pollTimerRef.current = setInterval(fetchIntrospection, pollInterval);
  }, [fetchIntrospection, pollInterval]);

  const stopPolling = useCallback(() => {
    setIsPolling(false);
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchIntrospection();
  }, [fetchIntrospection]);

  // Set up polling
  useEffect(() => {
    if (isPolling && pollInterval > 0) {
      pollTimerRef.current = setInterval(fetchIntrospection, pollInterval);
    }
    
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [isPolling, pollInterval, fetchIntrospection]);

  return {
    data,
    isLoading,
    error,
    refresh: fetchIntrospection,
    setLevel,
    level,
    isPolling,
    startPolling,
    stopPolling
  };
}

export default useIntrospection;
