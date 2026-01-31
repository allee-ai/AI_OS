/**
 * Introspection Service
 * =====================
 * API client for the /api/introspection endpoints.
 * Provides visibility into the agent's internal state for the viewer panel.
 */

import type { 
  IntrospectionData, 
  ThreadHealth, 
  IdentityFact, 
  ContextAssembly, 
  LogEvent 
} from '../types/introspection';
import { API_CONFIG } from '../utils/constants';

class IntrospectionService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_CONFIG.BASE_URL;
  }

  /**
   * Get full introspection data for the viewer panel.
   * @param level Context level (1=minimal, 2=moderate, 3=full)
   */
  async getIntrospection(level: number = 2): Promise<IntrospectionData> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.INTROSPECTION}?level=${level}`
    );

    if (!response.ok) {
      throw new Error(`Introspection error: ${response.status}`);
    }

    const data = await response.json();
    
    // Transform subconscious response to IntrospectionData format
    const threads: Record<string, any> = {};
    let totalFacts = 0;
    let threadCount = 0;
    
    if (data.state) {
      for (const [name, info] of Object.entries(data.state as Record<string, any>)) {
        threadCount++;
        const factCount = info.fact_count || 0;
        totalFacts += factCount;
        threads[name] = {
          name,
          status: info.health?.status || info.state?.status || 'unknown',
          message: info.health?.message || `${factCount} facts`,
          details: info.health?.details || {}
        };
      }
    }
    
    return {
      status: 'awake',
      overall_health: 'healthy',
      threads,
      identity_facts: [],
      recent_events: data.meta?.recent_events || [],
      context: {
        level,
        facts: [],
        fact_count: totalFacts,
        thread_count: threadCount,
        timestamp: new Date().toISOString()
      },
      context_level: level,
      relevance_scores: []
    };
  }

  /**
   * Get identity facts only.
   */
  async getIdentityFacts(level: number = 2): Promise<IdentityFact[]> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.INTROSPECTION_IDENTITY}?level=${level}`
    );

    if (!response.ok) {
      throw new Error(`Identity introspection error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Get health status of all registered threads.
   */
  async getThreadHealth(): Promise<Record<string, ThreadHealth>> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.INTROSPECTION_THREADS}`
    );

    if (!response.ok) {
      throw new Error(`Thread health error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Get assembled context at specified level.
   */
  async getContext(level: number = 2): Promise<ContextAssembly> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.INTROSPECTION_CONTEXT}?level=${level}`
    );

    if (!response.ok) {
      throw new Error(`Context assembly error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Get recent log events.
   */
  async getRecentEvents(limit: number = 20): Promise<LogEvent[]> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.INTROSPECTION_EVENTS}?limit=${limit}`
    );

    if (!response.ok) {
      throw new Error(`Events error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Manually add a log event.
   */
  async addEvent(payload: {
    event_type: string;
    data: string;
    source?: string;
    metadata?: Record<string, unknown>;
    session_id?: string;
    related_key?: string;
    related_table?: string;
  }): Promise<{ event_id: number; status: string }> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.INTROSPECTION_EVENTS}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }
    );

    if (!response.ok) {
      throw new Error(`Add event error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Trigger memory consolidation.
   * @param dryRun If true, score facts but don't actually consolidate
   */
  async consolidateMemory(dryRun: boolean = false): Promise<ConsolidationResult> {
    const response = await fetch(
      `${this.baseUrl}/api/introspection/consolidate?dry_run=${dryRun}`,
      { method: 'POST' }
    );

    if (!response.ok) {
      throw new Error(`Consolidation error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Get temp_memory stats.
   */
  async getMemoryStats(): Promise<{ pending: number; consolidated: number; total: number }> {
    const response = await fetch(`${this.baseUrl}/api/introspection/memory/stats`);
    if (!response.ok) {
      throw new Error(`Memory stats error: ${response.status}`);
    }
    return response.json();
  }
}

export interface ConsolidationResult {
  success: boolean;
  facts_processed: number;
  promoted_l2: number;
  promoted_l3: number;
  discarded: number;
  message: string;
}

// Export singleton instance
export const introspectionService = new IntrospectionService();
export default introspectionService;
