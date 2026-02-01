/**
 * Subconscious Page
 * =================
 * Standalone page for monitoring the AI's background processes.
 * Shows loops, temp facts, memory potentiation, and export controls.
 */

import { Link } from 'react-router-dom';
import SubconsciousDashboard from '../components/SubconsciousDashboard';
import './SubconsciousPage.css';

export const SubconsciousPage = () => {
  return (
    <div className="subconscious-page">
      <header className="subconscious-header">
        <Link to="/" className="back-link">← Home</Link>
        <h1>🧠 Subconscious</h1>
        <p className="header-desc">Background loops, memory consolidation, and training export</p>
      </header>
      
      <SubconsciousDashboard />
    </div>
  );
};

export default SubconsciousPage;
