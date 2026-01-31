import { Link } from 'react-router-dom';
import { WorkspacePanel } from '../components/WorkspacePanel';

export const WorkspacePage = () => {
  return (
    <div className="page-wrapper">
      <div className="page-header">
        <Link to="/" className="back-link">← Back</Link>
        <h1>📂 Workspace</h1>
      </div>
      <WorkspacePanel />
    </div>
  );
};
