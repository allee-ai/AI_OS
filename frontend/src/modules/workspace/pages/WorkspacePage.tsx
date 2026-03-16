import { WorkspacePanel } from '../components/WorkspacePanel';

export const WorkspacePage = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <WorkspacePanel />
      </div>
    </div>
  );
};
