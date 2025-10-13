import { Agent, Finding, AgentMetrics } from './Agent';

export interface Project {
  id: string;
  name: string;
  path: string;
  description?: string;
  created_at: string;
  last_activity: string;
  favorite: boolean;
  color?: string;
  tags?: string[];
  settings?: ProjectSettings;
}

export interface ProjectSettings {
  refresh_interval: number;
  auto_scroll_logs: boolean;
  show_debug_logs: boolean;
  notifications_enabled: boolean;
  max_log_lines: number;
  theme_override?: 'light' | 'dark' | 'auto';
}

export interface ProjectStatus {
  project: Project;
  agent_registry?: {
    task_id: string;
    description: string;
    created_at: string;
    agents: Agent[];
  };
  agents: Agent[];
  findings: Finding[];
  metrics: AgentMetrics;
  health: ProjectHealth;
  workspace_structure: WorkspaceStructure;
}

export interface ProjectHealth {
  status: 'healthy' | 'warning' | 'error' | 'offline';
  last_check: string;
  issues: HealthIssue[];
  uptime: number;
}

export interface HealthIssue {
  type: 'agents' | 'files' | 'permissions' | 'system';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  suggestion?: string;
  timestamp: string;
}

export interface WorkspaceStructure {
  has_agent_workspace: boolean;
  has_registry: boolean;
  has_findings: boolean;
  has_logs: boolean;
  has_progress: boolean;
  task_directories: string[];
  recent_tasks: RecentTask[];
}

export interface RecentTask {
  task_id: string;
  description: string;
  created_at: string;
  agent_count: number;
  status: 'active' | 'completed' | 'failed';
  last_activity: string;
}

export interface ProjectDiscovery {
  path: string;
  name: string;
  agent_workspace_path: string;
  last_modified: string;
  task_count: number;
  recent_activity: boolean;
  valid: boolean;
  error?: string;
}

export interface ProjectFilters {
  status?: ('healthy' | 'warning' | 'error' | 'offline')[];
  tags?: string[];
  search?: string;
  sort_by: 'name' | 'last_activity' | 'created_at' | 'agent_count';
  sort_order: 'asc' | 'desc';
  show_favorites_only: boolean;
}
