import { useState, useEffect } from 'react';

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  description?: string;
}

interface ModelDropdownProps {
  value: string;
  onChange: (modelId: string) => void;
  /** Only show models from this provider (e.g. 'ollama'). Omit to show all. */
  filterProvider?: string;
  className?: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  ollama: '💻 Ollama',
  openai: '🔑 OpenAI',
  http: '🌐 Custom',
};

let _cachedModels: ModelOption[] | null = null;
let _cacheTime = 0;
const CACHE_TTL = 30_000; // 30s

async function fetchModels(): Promise<ModelOption[]> {
  const now = Date.now();
  if (_cachedModels && now - _cacheTime < CACHE_TTL) return _cachedModels;

  try {
    const res = await fetch('/api/models');
    if (!res.ok) throw new Error('fetch failed');
    const data = await res.json();
    _cachedModels = data.models || [];
    _cacheTime = now;
    return _cachedModels!;
  } catch {
    return _cachedModels || [];
  }
}

/** Invalidate the shared cache so the next render re-fetches. */
export function invalidateModelCache() {
  _cachedModels = null;
  _cacheTime = 0;
}

/**
 * Shared model dropdown used everywhere a model needs to be selected.
 * Fetches the live model list from `/api/models` (with short cache).
 * Groups options by provider.
 */
export const ModelDropdown = ({ value, onChange, filterProvider, className }: ModelDropdownProps) => {
  const [models, setModels] = useState<ModelOption[]>([]);

  useEffect(() => {
    fetchModels().then(setModels);
  }, []);

  const filtered = filterProvider
    ? models.filter(m => m.provider === filterProvider)
    : models;

  // Group by provider for optgroup rendering
  const providers = [...new Set(filtered.map(m => m.provider))];

  // If the current value isn't in the list, add it as a placeholder
  const valueInList = filtered.some(m => m.id === value);

  return (
    <select
      className={className}
      value={value}
      onChange={e => onChange(e.target.value)}
    >
      {!valueInList && value && (
        <option value={value}>{value}</option>
      )}
      {providers.length <= 1
        ? filtered.map(m => (
            <option key={m.id} value={m.id}>
              {m.name}{m.description ? ` — ${m.description}` : ''}
            </option>
          ))
        : providers.map(p => (
            <optgroup key={p} label={PROVIDER_LABELS[p] || p}>
              {filtered.filter(m => m.provider === p).map(m => (
                <option key={m.id} value={m.id}>
                  {m.name}{m.description ? ` — ${m.description}` : ''}
                </option>
              ))}
            </optgroup>
          ))
      }
    </select>
  );
};
