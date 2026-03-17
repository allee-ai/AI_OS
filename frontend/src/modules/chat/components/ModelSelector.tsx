import React, { useState, useEffect, useRef } from 'react';
import type { ModelInfo } from '../types/chat';
import { apiService } from '../services/chatApi';
import './ModelSelector.css';

interface ModelSelectorProps {
  onModelChange?: (model: ModelInfo) => void;
}

const PROVIDER_LABELS: Record<string, string> = {
  ollama: 'Local (Ollama)',
  openai: 'OpenAI',
  http: 'Custom Endpoint',
};

const PROVIDER_ICONS: Record<string, string> = {
  ollama: '💻',
  openai: '🔑',
  http: '🌐',
};

export const ModelSelector: React.FC<ModelSelectorProps> = ({ onModelChange }) => {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [currentModel, setCurrentModel] = useState<string>('');
  const [_currentProvider, setCurrentProvider] = useState<string>('ollama');
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

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
        if (response.provider) {
          setCurrentProvider(response.provider);
        }
      } catch (error) {
        console.log('Using default models (backend not available)');
      }
    };
    loadModels();
  }, []);

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
      await apiService.setModel(model.id, model.provider);
      setCurrentModel(model.id);
      setCurrentProvider(model.provider);
      onModelChange?.(model);
    } catch (error) {
      apiService.setCurrentModelLocal(model.id);
      setCurrentModel(model.id);
      setCurrentProvider(model.provider);
      onModelChange?.(model);
    }
    setIsLoading(false);
    setIsOpen(false);
  };

  const selectedModel = models.find(m => m.id === currentModel) || models[0];

  // Group models by provider
  const providers = [...new Set(models.map(m => m.provider))];

  return (
    <div className="model-selector" ref={dropdownRef}>
      <button 
        className="model-selector-button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
      >
        <span className={`provider-badge ${selectedModel?.provider || 'ollama'}`}>
          {PROVIDER_ICONS[selectedModel?.provider || 'ollama'] || '💻'}
        </span>
        <span className="model-name">{selectedModel?.name || 'Select Model'}</span>
        <span className="dropdown-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="model-dropdown">
          {providers.map(provider => {
            const group = models.filter(m => m.provider === provider);
            if (group.length === 0) return null;
            return (
              <div className="model-group" key={provider}>
                <div className="model-group-label">
                  {PROVIDER_ICONS[provider] || '💻'} {PROVIDER_LABELS[provider] || provider}
                </div>
                {group.map(model => (
                  <button
                    key={model.id}
                    className={`model-option ${model.id === currentModel ? 'selected' : ''}`}
                    onClick={() => handleModelSelect(model)}
                  >
                    <div className="model-info">
                      <span className="model-option-name">{model.name}</span>
                      {model.description && <span className="model-description">{model.description}</span>}
                    </div>
                    {model.id === currentModel && <span className="check">✓</span>}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
