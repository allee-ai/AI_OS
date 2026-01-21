import React from 'react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

export const Sidebar: React.FC = () => {
  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">🧠</div>
        <h3>Dev Tools</h3>
      </div>
      <div className="sidebar-links">
        <NavLink to="/dev" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
           Fire-Tuner
        </NavLink>
        <NavLink to="/" className="nav-link">
           ← Back to App
        </NavLink>
      </div>
    </nav>
  );
};

