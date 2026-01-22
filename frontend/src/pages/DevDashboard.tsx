import React from 'react';
import { Sidebar } from '../components/Sidebar';
import { FinetunePanel } from '../components/dev/FinetunePanel';

export const DevDashboard: React.FC = () => {
    return (
        <div className="dashboard-container">
            <Sidebar />
            <div className="main-content">
                <FinetunePanel />
            </div>
        </div>
    );
};
