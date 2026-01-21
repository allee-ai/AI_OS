import { useState, useEffect } from 'react';

interface NolaMode {
  mode: 'personal' | 'demo';
  is_demo: boolean;
  is_dev: boolean;
}

export const useNolaMode = () => {
  const [modeInfo, setModeInfo] = useState<NolaMode>({
    mode: 'personal',
    is_demo: false,
    is_dev: false
  });
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchMode = async () => {
      try {
        // Use the db-mode endpoint for mode info
        const res = await fetch('/api/db-mode/mode');
        if (res.ok) {
          const data = await res.json();
          setModeInfo({
            mode: data.mode,
            is_demo: data.mode === 'demo',
            is_dev: false // Can be extended later
          });
        }
      } catch (err) {
        console.error('Failed to fetch mode:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchMode();
  }, []);
  
  return { ...modeInfo, loading };
};