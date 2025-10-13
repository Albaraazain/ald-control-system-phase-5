import React, { useState, useEffect } from 'react';
import { ProjectSidebar } from './components/ProjectSidebar';
import { AgentGrid } from './components/AgentGrid';
import { TaskTimeline } from './components/TaskTimeline';
import { FindingsPanel } from './components/FindingsPanel';
import { LogViewer } from './components/LogViewer';
import { ProjectOverview } from './components/ProjectOverview';
import { ProjectDiscovery, Project } from './types/Project';
import { Agent, AgentRegistry } from './types/Agent';
import { projectScanner } from './services/ProjectScanner';
import { useProjectStore } from './store/projectStore';
import { useTheme } from './hooks/useTheme';

const App: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const {
    projects,
    selectedProject,
    agents,
    setProjects,
    setSelectedProject,
    setAgents
  } = useProjectStore();

  const [isScanning, setIsScanning] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [showTimeline, setShowTimeline] = useState(false);

  // Initialize app and scan for projects
  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    setIsScanning(true);
    try {
      // Scan common directories for projects with .agent-workspace
      const homePath = process.env.HOME || process.env.USERPROFILE || '';
      const commonPaths = [
        homePath,
        `${homePath}/Documents`,
        `${homePath}/Projects`,
        `${homePath}/Development`,
        `${homePath}/Code`,
        '/Users',
        '/home'
      ];

      const allProjects: ProjectDiscovery[] = [];
      
      for (const scanPath of commonPaths) {
        try {
          const foundProjects = await projectScanner.scanDirectory(scanPath, 2);
          allProjects.push(...foundProjects);
        } catch (error) {
          console.warn(`Could not scan ${scanPath}:`, error);
        }
      }

      // Convert to Project objects and set
      const projectList: Project[] = allProjects.map(discovery => ({
        id: discovery.path,
        name: discovery.name,
        path: discovery.path,
        created_at: discovery.last_modified,
        last_activity: discovery.last_modified,
        favorite: false,
        tags: discovery.recent_activity ? ['recent'] : []
      }));

      setProjects(projectList);

      // Auto-select first project if available
      if (projectList.length > 0) {
        await selectProject(projectList[0]);
      }
    } catch (error) {
      console.error('Error initializing app:', error);
    } finally {
      setIsScanning(false);
    }
  };

  const selectProject = async (project: Project) => {
    setSelectedProject(project);
    
    try {
      // Load agent registry for selected project
      const registry = await projectScanner.loadAgentRegistry(project.path);
      if (registry) {
        setAgents(registry.agents);
      } else {
        setAgents([]);
      }
    } catch (error) {
      console.error('Error loading project agents:', error);
      setAgents([]);
    }
  };

  const handleAddProject = async () => {
    // This would open a directory picker dialog in the real app
    // For now, we'll implement a simple rescan
    await initializeApp();
  };

  const handleAgentSelect = (agent: Agent) => {
    setSelectedAgent(agent);
  };

  const handleRefresh = async () => {
    if (selectedProject) {
      await selectProject(selectedProject);
    }
  };

  return (
    <div className={`h-screen flex ${theme}`}>
      {/* Project Sidebar */}
      <div className="w-80 border-r border-border bg-card">
        <ProjectSidebar
          projects={projects}
          selectedProject={selectedProject}
          onProjectSelect={selectProject}
          onAddProject={handleAddProject}
          onRefresh={handleRefresh}
          isScanning={isScanning}
        />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="h-16 border-b border-border bg-card px-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold">Agent Visualizer</h1>
            {selectedProject && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>•</span>
                <span>{selectedProject.name}</span>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowTimeline(!showTimeline)}
              className="px-3 py-1 text-sm bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80"
            >
              {showTimeline ? 'Grid View' : 'Timeline'}
            </button>
            <button
              onClick={toggleTheme}
              className="px-3 py-1 text-sm bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80"
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {selectedProject ? (
            <>
              {/* Left Panel - Agents/Timeline */}
              <div className="flex-1 flex flex-col">
                {/* Project Overview */}
                <div className="p-4 border-b border-border">
                  <ProjectOverview
                    project={selectedProject}
                    agents={agents}
                  />
                </div>

                {/* Agents Grid or Timeline */}
                <div className="flex-1 p-4 overflow-auto">
                  {showTimeline ? (
                    <TaskTimeline
                      agents={agents}
                      onAgentSelect={handleAgentSelect}
                      selectedAgent={selectedAgent}
                    />
                  ) : (
                    <AgentGrid
                      agents={agents}
                      onAgentSelect={handleAgentSelect}
                      selectedAgent={selectedAgent}
                    />
                  )}
                </div>
              </div>

              {/* Right Panel - Details */}
              {selectedAgent && (
                <div className="w-96 border-l border-border bg-card flex flex-col">
                  {/* Agent Details Header */}
                  <div className="p-4 border-b border-border">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold">Agent Details</h3>
                      <button
                        onClick={() => setSelectedAgent(null)}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        ✕
                      </button>
                    </div>
                    <p className="text-sm text-muted-foreground">{selectedAgent.id}</p>
                  </div>

                  {/* Findings */}
                  <div className="flex-1 overflow-hidden">
                    <FindingsPanel
                      agent={selectedAgent}
                      projectPath={selectedProject.path}
                    />
                  </div>

                  {/* Logs */}
                  <div className="h-64 border-t border-border">
                    <LogViewer
                      agent={selectedAgent}
                      projectPath={selectedProject.path}
                    />
                  </div>
                </div>
              )}
            </>
          ) : (
            /* No Project Selected */
            <div className="flex-1 flex items-center justify-center text-center">
              <div className="max-w-md">
                <h2 className="text-2xl font-semibold mb-4">Welcome to Agent Visualizer</h2>
                <p className="text-muted-foreground mb-6">
                  {isScanning 
                    ? 'Scanning for projects with .agent-workspace directories...'
                    : projects.length === 0
                    ? 'No projects found. Add a project to get started.'
                    : 'Select a project from the sidebar to view its agents and progress.'
                  }
                </p>
                {!isScanning && projects.length === 0 && (
                  <button
                    onClick={handleAddProject}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                  >
                    Add Project
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
