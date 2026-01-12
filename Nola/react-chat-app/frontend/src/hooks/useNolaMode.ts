import { useState, useEffect } from 'react';

interface NolaMode {
  mode: 'personal' | 'demo';
  mode_set: boolean;
  dev_mode: boolean;
  is_demo: boolean;
  is_dev: boolean;
  build_method: 'local' | 'docker';
}

export const useNolaMode = () => {
  const [modeInfo, setModeInfo] = useState<NolaMode>({
    mode: 'personal',
    mode_set: false,
    dev_mode: false,
    is_demo: false,
    is_dev: false,
    build_method: 'local'
  });
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchMode = async () => {
      try {
        const res = await fetch('/api/services/mode');
        if (res.ok) {
          const data = await res.json();
          setModeInfo(data);
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