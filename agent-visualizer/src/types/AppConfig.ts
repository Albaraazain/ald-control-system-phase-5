export interface AppConfig {
  version: string;
  theme: 'light' | 'dark' | 'auto';
  projects: ProjectConfig[];
  preferences: AppPreferences;
  window: WindowConfig;
  notifications: NotificationConfig;
}

export interface ProjectConfig {
  id: string;
  name: string;
  path: string;
  favorite: boolean;
  color?: string;
  tags?: string[];
  last_opened: string;
  settings: ProjectSettings;
}

export interface ProjectSettings {
  refresh_interval: number;
  auto_scroll_logs: boolean;
  show_debug_logs: boolean;
  notifications_enabled: boolean;
  max_log_lines: number;
  theme_override?: 'light' | 'dark' | 'auto';
}

export interface AppPreferences {
  auto_discover_projects: boolean;
  default_refresh_interval: number;
  log_retention_days: number;
  enable_analytics: boolean;
  check_for_updates: boolean;
  start_minimized: boolean;
  close_to_tray: boolean;
}

export interface WindowConfig {
  width: number;
  height: number;
  x?: number;
  y?: number;
  maximized: boolean;
  sidebar_width: number;
  remember_position: boolean;
}

export interface NotificationConfig {
  enabled: boolean;
  agent_completion: boolean;
  agent_failure: boolean;
  system_warnings: boolean;
  sound_enabled: boolean;
  desktop_notifications: boolean;
}

export interface FileWatcherConfig {
  ignore_patterns: string[];
  debounce_ms: number;
  max_file_size: number;
  watch_subdirectories: boolean;
}
