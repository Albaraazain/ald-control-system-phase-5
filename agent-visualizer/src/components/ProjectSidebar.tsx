import React from 'react';
import { Project } from '../types/Project';

interface ProjectSidebarProps {
  projects: Project[];
  selectedProject: Project | null;
  onProjectSelect: (project: Project) => void;
  onAddProject: () => void;
  onRefresh: () => void;
  isScanning: boolean;
}

export const ProjectSidebar: React.FC<ProjectSidebarProps> = ({
  projects,
  selectedProject,
  onProjectSelect,
  onAddProject,
  onRefresh,
  isScanning
}) => {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Projects</h2>
          <div className="flex gap-2">
            <button
              onClick={onRefresh}
              disabled={isScanning}
              className="p-2 text-sm bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 disabled:opacity-50"
              title="Refresh"
            >
              {isScanning ? '⟳' : '↻'}
            </button>
            <button
              onClick={onAddProject}
              className="p-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              title="Add Project"
            >
              +
            </button>
          </div>
        </div>
        
        {isScanning && (
          <div className="text-sm text-muted-foreground">
            Scanning for projects...
          </div>
        )}
      </div>

      {/* Project List */}
      <div className="flex-1 overflow-auto p-2">
        {projects.length === 0 ? (
          <div className="text-center text-muted-foreground p-4">
            {isScanning ? 'Searching...' : 'No projects found'}
          </div>
        ) : (
          <div className="space-y-1">
            {projects.map((project) => (
              <button
                key={project.id}
                onClick={() => onProjectSelect(project)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedProject?.id === project.id
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-card hover:bg-muted border-border'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{project.name}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {project.path}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 ml-2">
                    {project.favorite && (
                      <span className="text-yellow-500">★</span>
                    )}
                    {project.tags?.includes('recent') && (
                      <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-border">
        <div className="text-xs text-muted-foreground">
          {projects.length} project{projects.length !== 1 ? 's' : ''} found
        </div>
      </div>
    </div>
  );
};
