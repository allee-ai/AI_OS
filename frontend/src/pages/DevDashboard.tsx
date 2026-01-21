import React from 'react';
import { Sidebar } from '../components/Sidebar';
import { FinetunePanel } from '../components/dev/FinetunePanel';
import { useNolaMode } from '../hooks/useNolaMode';

export const DevDashboard: React.FC = () => {
    const { is_dev } = useNolaMode();

    if (!is_dev) {
        return (
            <div className="dashboard-container">
                <Sidebar />
                <div className="main-content">
                    <h1>Restricted</h1>
                    <p>Developer mode required.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="dashboard-container">
            <Sidebar />
            <div className="main-content">
                <FinetunePanel />
            </div>
        </div>
    );
};
