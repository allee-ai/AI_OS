/**
 * Introspection Types
 * ====================
 * TypeScript types for the /api/introspection endpoint.
 * Mirrors the Pydantic models in backend/api/introspection.py
 */

/** Health status for a single thread adapter */
export interface ThreadHealth {
  name: string;
  status: 'ok' | 'degraded' | 'error' | 'unknown';
  message: string;
  last_sync?: string;
  details: Record<string, unknown>;
}

/** A single fact from identity introspection */
export interface IdentityFact {
  source: 'machineID' | 'userID' | 'config' | 'error';
  fact: string;
  context_level: number;
}

/** A recent log event */
export interface LogEvent {
  timestamp: string;
  event_type: string;
  source: string;
  message: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
}

/** Assembled context from subconscious */
export interface ContextAssembly {
  level: number;
  facts: string[];
  fact_count: number;
  thread_count: number;
  timestamp: string;
}

/** Relevance score row */
export interface RelevanceScore {
  key: string;
  score: number;
  weight: number;
  context_level: number;
  updated_at?: string;
}

/** Full introspection response for the viewer */
export interface IntrospectionData {
  status: 'awake' | 'asleep' | 'error';
  wake_time?: string;
  overall_health: 'healthy' | 'degraded' | 'error' | 'unknown';
  
  // Thread-level data
  threads: Record<string, ThreadHealth>;
  
  // Identity facts
  identity_facts: IdentityFact[];
  
  // Recent events  
  recent_events: LogEvent[];
  
  // Context assembly preview
  context?: ContextAssembly;
  
  // Session info
  session_id?: string;
  context_level: number;

  // Relevance
  relevance_scores: RelevanceScore[];
}

/** Context level descriptions for UI */
export const CONTEXT_LEVELS = {
  1: { name: 'Minimal', description: 'Real-time, ultra-fast responses', icon: '⚡' },
  2: { name: 'Moderate', description: 'Conversational, balanced context', icon: '💬' },
  3: { name: 'Full', description: 'Deep analysis, full state access', icon: '🔬' },
} as const;

/** Thread status colors for UI */
export const STATUS_COLORS = {
  ok: '#22c55e',      // green
  healthy: '#22c55e',
  degraded: '#f59e0b', // amber
  warning: '#f59e0b',
  error: '#ef4444',    // red
  unknown: '#6b7280',  // gray
  awake: '#22c55e',
  asleep: '#6b7280',
} as const;
