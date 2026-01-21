import React, { useState, useEffect, useRef } from 'react';
import type { ModelInfo } from '../../types/chat';
import { apiService } from '../../services/api';
import './ModelSelector.css';

interface ModelSelectorProps {
  onModelChange?: (model: ModelInfo) => void;
}

// Default models - backend can override these
const DEFAULT_MODELS: ModelInfo[] = [
  { id: 'qwen2.5:7b', name: 'Qwen 2.5 7B', provider: 'ollama', description: 'Local (default)' },
  { id: 'deepseek-v3.1:671b', name: 'DeepSeek V3.1', provider: 'cloud', description: '671B hybrid thinking' },
  { id: 'gpt-oss:120b', name: 'GPT-OSS', provider: 'cloud', description: '120B high-reasoning' },
  { id: 'qwen3-coder:480b', name: 'Qwen3 Coder', provider: 'cloud', description: '480B agentic/coding' },
  { id: 'kimi-k2:1t', name: 'Kimi K2', provider: 'cloud', description: '1T MoE agent' },
  { id: 'qwen3-vl:235b', name: 'Qwen3 VL', provider: 'cloud', description: '235B vision-language' },
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash', provider: 'cloud', description: 'High-speed multimodal' },
  { id: 'gemini-3-pro-preview', name: 'Gemini 3 Pro', provider: 'cloud', description: 'Frontier intelligence' },
];

export const ModelSelector: React.FC<ModelSelectorProps> = ({ onModelChange }) => {
  const [models, setModels] = useState<ModelInfo[]>(DEFAULT_MODELS);
  const [currentModel, setCurrentModel] = useState<string>('qwen2.5:7b');
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load models from backend on mount
  useEffect(() => {
    const loadModels = async () => {
      try {
        const response = await apiService.getModels();
        if (response.models?.length > 0) {
          setModels(response.models);
        }
        if (response.current) {
          setCurrentModel(response.current);
          apiService.setCurrentModelLocal(response.current);
        }
      } catch (error) {
        // Use defaults if backend doesn't have model endpoint yet
        console.log('Using default models (backend endpoint not available)');
      }
    };
    loadModels();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleModelSelect = async (model: ModelInfo) => {
    setIsLoading(true);
    try {
      await apiService.setModel(model.id);
      setCurrentModel(model.id);
      onModelChange?.(model);
    } catch (error) {
      // Even if backend fails, update locally for next message
      apiService.setCurrentModelLocal(model.id);
      setCurrentModel(model.id);
      onModelChange?.(model);
    }
    setIsLoading(false);
    setIsOpen(false);
  };

  const selectedModel = models.find(m => m.id === currentModel) || models[0];

  return (
    <div className="model-selector" ref={dropdownRef}>
      <button 
        className="model-selector-button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
      >
        <span className={`provider-badge ${selectedModel?.provider || 'ollama'}`}>
          {selectedModel?.provider === 'cloud' ? '☁️' : '💻'}
        </span>
        <span className="model-name">{selectedModel?.name || 'Select Model'}</span>
        <span className="dropdown-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="model-dropdown">
          <div className="model-group">
            <div className="model-group-label">Local (Ollama)</div>
            {models.filter(m => m.provider === 'ollama').map(model => (
              <button
                key={model.id}
                className={`model-option ${model.id === currentModel ? 'selected' : ''}`}
                onClick={() => handleModelSelect(model)}
              >
                <span className="provider-badge ollama">💻</span>
                <div className="model-info">
                  <span className="model-option-name">{model.name}</span>
                  {model.description && <span className="model-description">{model.description}</span>}
                </div>
                {model.id === currentModel && <span className="check">✓</span>}
              </button>
            ))}
          </div>
          
          <div className="model-group">
            <div className="model-group-label">Cloud</div>
            {models.filter(m => m.provider === 'cloud').map(model => (
              <button
                key={model.id}
                className={`model-option ${model.id === currentModel ? 'selected' : ''}`}
                onClick={() => handleModelSelect(model)}
              >
                <span className="provider-badge cloud">☁️</span>
                <div className="model-info">
                  <span className="model-option-name">{model.name}</span>
                  {model.description && <span className="model-description">{model.description}</span>}
                </div>
                {model.id === currentModel && <span className="check">✓</span>}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
