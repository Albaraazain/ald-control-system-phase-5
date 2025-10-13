import React from 'react';
import { Project } from '../types/Project';
import { Agent } from '../types/Agent';

interface ProjectOverviewProps {
  project: Project;
  agents: Agent[];
}

export const ProjectOverview: React.FC<ProjectOverviewProps> = ({
  project,
  agents
}) => {
  const runningAgents = agents.filter(a => a.status === 'running').length;
  const completedAgents = agents.filter(a => a.status === 'completed').length;
  const failedAgents = agents.filter(a => a.status === 'failed').length;
  const avgProgress = agents.length > 0 
    ? Math.round(agents.reduce((sum, a) => sum + a.progress, 0) / agents.length)
    : 0;

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">{project.name}</h3>
        <div className="text-sm text-muted-foreground">
          Last activity: {new Date(project.last_activity).toLocaleString()}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-primary">{agents.length}</div>
          <div className="text-sm text-muted-foreground">Total Agents</div>
        </div>
        
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-600">{runningAgents}</div>
          <div className="text-sm text-muted-foreground">Running</div>
        </div>
        
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">{completedAgents}</div>
          <div className="text-sm text-muted-foreground">Completed</div>
        </div>
        
        <div className="text-center">
          <div className="text-2xl font-bold text-red-600">{failedAgents}</div>
          <div className="text-sm text-muted-foreground">Failed</div>
        </div>
      </div>

      {agents.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-muted-foreground">Overall Progress</span>
            <span className="font-medium">{avgProgress}%</span>
          </div>
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className="h-full bg-primary rounded-full transition-all duration-300"
              style={{ width: `${avgProgress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
};
