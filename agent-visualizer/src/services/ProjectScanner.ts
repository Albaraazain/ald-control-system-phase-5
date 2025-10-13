import * as fs from 'fs';
import * as path from 'path';
import { ProjectDiscovery, Project, WorkspaceStructure } from '../types/Project';
import { AgentRegistry } from '../types/Agent';

export class ProjectScanner {
  private static instance: ProjectScanner;
  private discoveredProjects: Map<string, ProjectDiscovery> = new Map();

  public static getInstance(): ProjectScanner {
    if (!ProjectScanner.instance) {
      ProjectScanner.instance = new ProjectScanner();
    }
    return ProjectScanner.instance;
  }

  /**
   * Scan a directory recursively for .agent-workspace folders
   */
  public async scanDirectory(rootPath: string, maxDepth: number = 3): Promise<ProjectDiscovery[]> {
    const projects: ProjectDiscovery[] = [];
    
    try {
      await this.scanDirectoryRecursive(rootPath, 0, maxDepth, projects);
      
      // Update internal cache
      projects.forEach(project => {
        this.discoveredProjects.set(project.path, project);
      });
      
      return projects;
    } catch (error) {
      console.error('Error scanning directory:', error);
      return [];
    }
  }

  /**
   * Recursive directory scanning implementation
   */
  private async scanDirectoryRecursive(
    dirPath: string, 
    currentDepth: number, 
    maxDepth: number, 
    results: ProjectDiscovery[]
  ): Promise<void> {
    if (currentDepth > maxDepth) return;

    try {
      const entries = await fs.promises.readdir(dirPath, { withFileTypes: true });
      
      // Check if current directory has .agent-workspace
      const hasAgentWorkspace = entries.some(entry => 
        entry.isDirectory() && entry.name === '.agent-workspace'
      );

      if (hasAgentWorkspace) {
        const projectDiscovery = await this.analyzeProject(dirPath);
        if (projectDiscovery.valid) {
          results.push(projectDiscovery);
        }
      }

      // Continue scanning subdirectories
      for (const entry of entries) {
        if (entry.isDirectory() && !entry.name.startsWith('.') && !this.isIgnoredDirectory(entry.name)) {
          const subDirPath = path.join(dirPath, entry.name);
          await this.scanDirectoryRecursive(subDirPath, currentDepth + 1, maxDepth, results);
        }
      }
    } catch (error) {
      // Skip directories we can't read (permissions, etc.)
      console.warn(`Cannot scan directory ${dirPath}:`, error);
    }
  }

  /**
   * Analyze a project directory with .agent-workspace
   */
  public async analyzeProject(projectPath: string): Promise<ProjectDiscovery> {
    const agentWorkspacePath = path.join(projectPath, '.agent-workspace');
    const projectName = path.basename(projectPath);

    try {
      const stats = await fs.promises.stat(agentWorkspacePath);
      const taskDirs = await this.getTaskDirectories(agentWorkspacePath);
      
      return {
        path: projectPath,
        name: projectName,
        agent_workspace_path: agentWorkspacePath,
        last_modified: stats.mtime.toISOString(),
        task_count: taskDirs.length,
        recent_activity: this.hasRecentActivity(stats.mtime),
        valid: true
      };
    } catch (error) {
      return {
        path: projectPath,
        name: projectName,
        agent_workspace_path: agentWorkspacePath,
        last_modified: new Date().toISOString(),
        task_count: 0,
        recent_activity: false,
        valid: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Get workspace structure details
   */
  public async getWorkspaceStructure(agentWorkspacePath: string): Promise<WorkspaceStructure> {
    try {
      const entries = await fs.promises.readdir(agentWorkspacePath, { withFileTypes: true });
      const taskDirectories = await this.getTaskDirectories(agentWorkspacePath);
      const recentTasks = await this.getRecentTasks(agentWorkspacePath, taskDirectories);

      return {
        has_agent_workspace: true,
        has_registry: entries.some(e => e.name === 'AGENT_REGISTRY.json'),
        has_findings: entries.some(e => e.isDirectory() && e.name === 'findings'),
        has_logs: entries.some(e => e.isDirectory() && e.name === 'logs'),
        has_progress: entries.some(e => e.isDirectory() && e.name === 'progress'),
        task_directories: taskDirectories,
        recent_tasks: recentTasks
      };
    } catch (error) {
      return {
        has_agent_workspace: false,
        has_registry: false,
        has_findings: false,
        has_logs: false,
        has_progress: false,
        task_directories: [],
        recent_tasks: []
      };
    }
  }

  /**
   * Load agent registry from a project
   */
  public async loadAgentRegistry(projectPath: string): Promise<AgentRegistry | null> {
    try {
      const registryPath = path.join(projectPath, '.agent-workspace', 'AGENT_REGISTRY.json');
      const registryContent = await fs.promises.readFile(registryPath, 'utf-8');
      return JSON.parse(registryContent) as AgentRegistry;
    } catch (error) {
      // Try to find the most recent task registry
      return await this.loadMostRecentTaskRegistry(projectPath);
    }
  }

  /**
   * Load agent registry from the most recent task directory
   */
  private async loadMostRecentTaskRegistry(projectPath: string): Promise<AgentRegistry | null> {
    try {
      const agentWorkspacePath = path.join(projectPath, '.agent-workspace');
      const taskDirs = await this.getTaskDirectories(agentWorkspacePath);
      
      if (taskDirs.length === 0) return null;

      // Sort by modification time, most recent first
      const taskDirsWithStats = await Promise.all(
        taskDirs.map(async (taskDir) => {
          const taskPath = path.join(agentWorkspacePath, taskDir);
          const stats = await fs.promises.stat(taskPath);
          return { name: taskDir, path: taskPath, mtime: stats.mtime };
        })
      );

      taskDirsWithStats.sort((a, b) => b.mtime.getTime() - a.mtime.getTime());

      // Try to load registry from the most recent task
      for (const taskDir of taskDirsWithStats) {
        try {
          const registryPath = path.join(taskDir.path, 'AGENT_REGISTRY.json');
          const registryContent = await fs.promises.readFile(registryPath, 'utf-8');
          return JSON.parse(registryContent) as AgentRegistry;
        } catch (error) {
          continue; // Try next task directory
        }
      }

      return null;
    } catch (error) {
      console.error('Error loading most recent task registry:', error);
      return null;
    }
  }

  /**
   * Get all task directories from agent workspace
   */
  private async getTaskDirectories(agentWorkspacePath: string): Promise<string[]> {
    try {
      const entries = await fs.promises.readdir(agentWorkspacePath, { withFileTypes: true });
      return entries
        .filter(entry => entry.isDirectory() && (
          entry.name.startsWith('TASK-') || 
          entry.name.startsWith('task-') ||
          entry.name.includes('task')
        ))
        .map(entry => entry.name)
        .sort();
    } catch (error) {
      return [];
    }
  }

  /**
   * Get recent tasks with metadata
   */
  private async getRecentTasks(agentWorkspacePath: string, taskDirs: string[]) {
    const recentTasks = [];
    
    for (const taskDir of taskDirs.slice(-10)) { // Get last 10 tasks
      try {
        const taskPath = path.join(agentWorkspacePath, taskDir);
        const registryPath = path.join(taskPath, 'AGENT_REGISTRY.json');
        
        if (await this.fileExists(registryPath)) {
          const registryContent = await fs.promises.readFile(registryPath, 'utf-8');
          const registry = JSON.parse(registryContent) as AgentRegistry;
          const stats = await fs.promises.stat(taskPath);
          
          recentTasks.push({
            task_id: registry.task_id,
            description: registry.description,
            created_at: registry.created_at,
            agent_count: registry.agents.length,
            status: this.determineTaskStatus(registry.agents),
            last_activity: stats.mtime.toISOString()
          });
        }
      } catch (error) {
        // Skip invalid task directories
        continue;
      }
    }
    
    return recentTasks.sort((a, b) => 
      new Date(b.last_activity).getTime() - new Date(a.last_activity).getTime()
    );
  }

  /**
   * Determine task status based on agent statuses
   */
  private determineTaskStatus(agents: any[]): 'active' | 'completed' | 'failed' {
    const hasRunning = agents.some(agent => agent.status === 'running');
    const hasFailed = agents.some(agent => agent.status === 'failed');
    const allCompleted = agents.every(agent => agent.status === 'completed');

    if (hasRunning) return 'active';
    if (hasFailed) return 'failed';
    if (allCompleted) return 'completed';
    return 'active'; // Default fallback
  }

  /**
   * Check if a file exists
   */
  private async fileExists(filePath: string): Promise<boolean> {
    try {
      await fs.promises.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if directory has recent activity (within last 24 hours)
   */
  private hasRecentActivity(lastModified: Date): boolean {
    const oneDayAgo = new Date();
    oneDayAgo.setDate(oneDayAgo.getDate() - 1);
    return lastModified > oneDayAgo;
  }

  /**
   * Check if directory should be ignored during scanning
   */
  private isIgnoredDirectory(dirName: string): boolean {
    const ignoredDirs = [
      'node_modules',
      '.git',
      'dist',
      'build',
      'out',
      '.next',
      '.nuxt',
      'coverage',
      '.nyc_output',
      'tmp',
      'temp',
      'cache',
      '.cache'
    ];
    return ignoredDirs.includes(dirName);
  }

  /**
   * Watch a project directory for changes
   */
  public watchProject(projectPath: string, callback: (event: string, filename: string) => void): fs.FSWatcher {
    const agentWorkspacePath = path.join(projectPath, '.agent-workspace');
    return fs.watch(agentWorkspacePath, { recursive: true }, (event, filename) => {
      if (filename) {
        callback(event, filename);
      }
    });
  }

  /**
   * Get cached project discovery results
   */
  public getCachedProjects(): ProjectDiscovery[] {
    return Array.from(this.discoveredProjects.values());
  }

  /**
   * Clear the project cache
   */
  public clearCache(): void {
    this.discoveredProjects.clear();
  }
}

// Export singleton instance
export const projectScanner = ProjectScanner.getInstance();
