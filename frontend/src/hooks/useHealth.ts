import { useState, useEffect } from 'react';
import type { HealthStatus } from '../types';
import { fetchHealth } from '../services/api';

/**
 * Hook that polls the backend health-check endpoint.
 */
export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const data = await fetchHealth();
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Connection failed');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    check();
    return () => {
      cancelled = true;
    };
  }, []);

  return { health, error, loading };
}
