import { useState, useEffect } from 'react';

interface AppMode {
  mode: 'personal' | 'demo';
  is_demo: boolean;
}

export const useAppMode = () => {
  const [modeInfo, setModeInfo] = useState<AppMode>({
    mode: 'personal',
    is_demo: false
  });
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchMode = async () => {
      try {
        const res = await fetch('/api/db-mode/mode');
        if (res.ok) {
          const data = await res.json();
          setModeInfo({
            mode: data.mode,
            is_demo: data.mode === 'demo'
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