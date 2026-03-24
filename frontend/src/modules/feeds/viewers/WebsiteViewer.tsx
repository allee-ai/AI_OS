import { useState, useEffect, useRef } from 'react';
import { BASE_URL } from '../../../config/api';
import './FeedViewer.css';

const API_BASE = BASE_URL;

export default function WebsiteViewer() {
  const [url, setUrl] = useState('');
  const [inputUrl, setInputUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/feeds/website/url`)
      .then(r => r.json())
      .then(data => {
        setUrl(data.url);
        setInputUrl(data.url);
      })
      .catch(() => {
        setUrl('https://allee-ai.com');
        setInputUrl('https://allee-ai.com');
      })
      .finally(() => setLoading(false));
  }, []);

  const navigate = () => {
    let target = inputUrl.trim();
    if (!target) return;
    if (!/^https?:\/\//i.test(target)) {
      target = 'https://' + target;
      setInputUrl(target);
    }
    setUrl(target);
    fetch(`${API_BASE}/api/feeds/website/url`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: target }),
    }).catch(() => {});
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') navigate();
  };

  const reload = () => {
    if (iframeRef.current) {
      iframeRef.current.src = url;
    }
  };

  if (loading) {
    return (
      <div className="feed-viewer">
        <div className="viewer-loading">Loading website viewer…</div>
      </div>
    );
  }

  return (
    <div className="feed-viewer website-viewer">
      <div className="website-toolbar">
        <button className="website-btn" onClick={reload} title="Reload">↻</button>
        <input
          className="website-url-input"
          type="text"
          value={inputUrl}
          onChange={e => setInputUrl(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter URL…"
        />
        <button className="website-btn website-go-btn" onClick={navigate}>Go</button>
      </div>
      <div className="website-frame-wrapper">
        <iframe
          ref={iframeRef}
          src={url}
          className="website-frame"
          title="Website Viewer"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      </div>
    </div>
  );
}
