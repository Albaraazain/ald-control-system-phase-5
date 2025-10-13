import React from 'react';
import { Agent } from '../types/Agent';

interface TaskTimelineProps {
  agents: Agent[];
  onAgentSelect: (agent: Agent) => void;
  selectedAgent: Agent | null;
}

export const TaskTimeline: React.FC<TaskTimelineProps> = ({
  agents,
  onAgentSelect,
  selectedAgent
}) => {
  return (
    <div className="space-y-4">
      <div className="text-lg font-semibold mb-4">Task Timeline</div>
      
      {agents.length === 0 ? (
        <div className="text-center text-muted-foreground py-8">
          No agents to display in timeline
        </div>
      ) : (
        <div className="space-y-3">
          {agents.map((agent, index) => (
            <div
              key={agent.id}
              onClick={() => onAgentSelect(agent)}
              className={`flex items-center gap-4 p-3 rounded-lg border cursor-pointer ${
                selectedAgent?.id === agent.id
                  ? 'border-primary bg-primary/5'
                  : 'border-border bg-card hover:bg-muted/50'
              }`}
            >
              <div className="flex-shrink-0">
                <div className="w-4 h-4 bg-primary rounded-full"></div>
                {index < agents.length - 1 && (
                  <div className="w-0.5 h-6 bg-border mx-auto mt-2"></div>
                )}
              </div>
              
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{agent.type} - {agent.id}</div>
                  <div className="text-sm text-muted-foreground">
                    {new Date(agent.last_update).toLocaleTimeString()}
                  </div>
                </div>
                <div className="text-sm text-muted-foreground">
                  Status: {agent.status} • Progress: {agent.progress}%
                </div>
                {agent.prompt_summary && (
                  <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {agent.prompt_summary}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
