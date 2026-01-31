import React, { useState } from 'react';

export const FinetunePanel: React.FC = () => {
    const [config, setConfig] = useState({
        rank: 8,
        alpha: 16,
        learning_rate: 0.00001,
        batch_size: 1,
        iters: 600
    });
    const [status, setStatus] = useState<'idle' | 'running' | 'complete' | 'error'>('idle');
    const [logs, setLogs] = useState<string[]>([]);

    const handleStart = async () => {
        setStatus('running');
        setLogs(prev => [...prev, "🚀 Starting training job..."]);
        
        try {
            const res = await fetch('/api/finetune/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(config)
            });
            if (res.ok) {
                setLogs(prev => [...prev, "🌀 Job started. Check terminal for heat/progress."]);
                setStatus('complete'); 
            } else {
                throw new Error("Failed to start");
            }
        } catch (e) {
            setStatus('error');
            setLogs(prev => [...prev, "❌ Error starting training job."]);
        }
    };

    return (
        <div className="finetune-panel">
            <header style={{ marginBottom: '20px' }}>
                <h2>🔥 Fine-Tuner (M4 Air Optimized)</h2>
                <p>Train custom LoRA adapters on local data</p>
            </header>

            <div className="config-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                <div className="config-panel">
                    <div className="control-group">
                        <label>LoRA Rank (Complexity): {config.rank}</label>
                        <input 
                            type="range" min="4" max="32" step="4" 
                            value={config.rank}
                            onChange={e => setConfig({...config, rank: parseInt(e.target.value)})}
                        />
                        <small>Higher = Smarter but Slower. 8 is recommended.</small>
                    </div>

                    <div className="control-group">
                        <label>Alpha (Strength): {config.alpha}</label>
                        <input 
                            type="range" min="8" max="64" step="8" 
                            value={config.alpha}
                            onChange={e => setConfig({...config, alpha: parseInt(e.target.value)})}
                        />
                    </div>
                     <div className="control-group">
                        <label>Iterations: {config.iters}</label>
                        <input 
                            type="number" 
                            value={config.iters}
                            onChange={e => setConfig({...config, iters: parseInt(e.target.value)})}
                        />
                    </div>

                    <button 
                        className="action-button primary"
                        onClick={handleStart}
                        disabled={status === 'running'}
                        style={{marginTop: '20px'}}
                    >
                        {status === 'running' ? 'Training...' : '🔥 Start Training'}
                    </button>
                </div>

                <div className="logs-console" style={{
                    background: '#000', 
                    color: '#0f0', 
                    padding: '10px', 
                    fontFamily: 'monospace',
                    borderRadius: '4px',
                    height: '100%',
                    minHeight: '200px',
                    overflowY: 'auto'
                }}>
                    {logs.map((L, i) => <div key={i}>{L}</div>)}
                    {logs.length === 0 && <div>Ready to train...</div>}
                </div>
            </div>
        </div>
    );
};
