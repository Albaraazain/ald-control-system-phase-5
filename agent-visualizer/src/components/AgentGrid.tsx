import React from 'react';
import { Agent } from '../types/Agent';

interface AgentGridProps {
  agents: Agent[];
  onAgentSelect: (agent: Agent) => void;
  selectedAgent: Agent | null;
}

const getStatusColor = (status: Agent['status']) => {
  switch (status) {
    case 'running': return 'bg-blue-500';
    case 'completed': return 'bg-green-500';
    case 'failed': return 'bg-red-500';
    case 'paused': return 'bg-yellow-500';
    case 'idle': return 'bg-gray-500';
    default: return 'bg-gray-500';
  }
};

const getTypeIcon = (type: Agent['type']) => {
  switch (type) {
    case 'worker': return '⚡';
    case 'coordinator': return '🎯';
    case 'supervisor': return '👁️';
    case 'monitor': return '📊';
    default: return '🤖';
  }
};

export const AgentGrid: React.FC<AgentGridProps> = ({
  agents,
  onAgentSelect,
  selectedAgent
}) => {
  if (agents.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        <div className="text-center">
          <div className="text-4xl mb-4">🤖</div>
          <div>No agents found</div>
          <div className="text-sm mt-2">
            Agents will appear here when they are active in the project
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {agents.map((agent) => (
        <div
          key={agent.id}
          onClick={() => onAgentSelect(agent)}
          className={`agent-card p-4 border rounded-lg cursor-pointer ${
            selectedAgent?.id === agent.id
              ? 'border-primary bg-primary/5'
              : 'border-border bg-card hover:bg-muted/50'
          }`}
        >
          {/* Agent Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{getTypeIcon(agent.type)}</span>
              <div>
                <div className="font-medium text-sm">{agent.type}</div>
                <div className="text-xs text-muted-foreground truncate">
                  {agent.id}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div
                className={`w-3 h-3 rounded-full ${getStatusColor(agent.status)} ${
                  agent.status === 'running' ? 'agent-running' : ''
                }`}
              />
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mb-3">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-medium">{agent.progress}%</span>
            </div>
            <div className="w-full bg-muted rounded-full h-2 relative overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  agent.status === 'running' ? 'progress-shine' : ''
                } ${
                  agent.status === 'completed' 
                    ? 'bg-green-500' 
                    : agent.status === 'failed'
                    ? 'bg-red-500'
                    : 'bg-primary'
                }`}
                style={{ width: `${agent.progress}%` }}
              />
            </div>
          </div>

          {/* Agent Details */}
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status:</span>
              <span className={`font-medium capitalize ${
                agent.status === 'running' ? 'text-blue-600' :
                agent.status === 'completed' ? 'text-green-600' :
                agent.status === 'failed' ? 'text-red-600' :
                'text-muted-foreground'
              }`}>
                {agent.status}
              </span>
            </div>
            
            {agent.model && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Model:</span>
                <span className="font-mono">{agent.model}</span>
              </div>
            )}

            {agent.tmux_session && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Session:</span>
                <span className="font-mono">{agent.tmux_session}</span>
              </div>
            )}

            <div className="flex justify-between">
              <span className="text-muted-foreground">Updated:</span>
              <span>{new Date(agent.last_update).toLocaleTimeString()}</span>
            </div>
          </div>

          {/* Prompt Summary */}
          {agent.prompt_summary && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="text-xs text-muted-foreground mb-1">Task:</div>
              <div className="text-xs line-clamp-2">{agent.prompt_summary}</div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
