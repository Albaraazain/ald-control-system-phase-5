export interface Agent {
  id: string;
  type: 'worker' | 'coordinator' | 'supervisor' | 'monitor';
  tmux_session?: string;
  status: 'running' | 'completed' | 'failed' | 'paused' | 'idle';
  progress: number;
  started_at: string;
  last_update: string;
  prompt_summary?: string;
  model?: string;
  reasoning?: string | null;
  profile?: string | null;
  engine?: string;
  role?: string;
  linked_to?: string | null;
}

export interface AgentRegistry {
  task_id: string;
  description: string;
  created_at: string;
  agents: Agent[];
}

export interface Finding {
  id?: string;
  agent_id: string;
  type: 'info' | 'warning' | 'error' | 'success' | 'debug';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: string;
  metadata?: Record<string, any>;
  file_path?: string;
  line_number?: number;
  context?: string;
}

export interface AgentMetrics {
  total_agents: number;
  running_agents: number;
  completed_agents: number;
  failed_agents: number;
  average_progress: number;
  last_activity: string;
  uptime: number;
}

export interface AgentStatus {
  agent: Agent;
  findings: Finding[];
  logs: string[];
  metrics: {
    execution_time: number;
    memory_usage?: number;
    cpu_usage?: number;
    files_modified: number;
    commands_executed: number;
  };
}
