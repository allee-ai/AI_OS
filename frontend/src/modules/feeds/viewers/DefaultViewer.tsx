import './FeedViewer.css';
import ConnectPanel from './ConnectPanel';

interface Props {
  feedName: string;
}

export default function DefaultViewer({ feedName }: Props) {
  return (
    <div className="feed-viewer default-viewer">
      <div className="viewer-content">
        <ConnectPanel feed={feedName} />
        <div className="empty-state">
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔌</div>
          <div>Connect {feedName} to see messages here</div>
          <small>Once connected, you'll see inbox, drafts, and compose options</small>
        </div>
      </div>
    </div>
  );
}
