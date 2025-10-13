import React from 'react';
import { Agent } from '../types/Agent';

interface LogViewerProps {
  agent: Agent;
  projectPath: string;
}

export const LogViewer: React.FC<LogViewerProps> = ({
  agent,
  projectPath
}) => {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between">
          <h4 className="font-semibold">Logs</h4>
          <div className="flex gap-2">
            <button className="text-xs px-2 py-1 bg-secondary text-secondary-foreground rounded hover:bg-secondary/80">
              Clear
            </button>
            <button className="text-xs px-2 py-1 bg-secondary text-secondary-foreground rounded hover:bg-secondary/80">
              Download
            </button>
          </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto bg-black text-green-400 font-mono text-xs p-3">
        <div className="space-y-1">
          <div className="text-muted-foreground"># Agent {agent.id} logs</div>
          <div className="text-muted-foreground"># Status: {agent.status}</div>
          <div className="text-muted-foreground"># Progress: {agent.progress}%</div>
          <div className="text-muted-foreground"># Last update: {agent.last_update}</div>
          <div className="text-muted-foreground"># ===================================</div>
          <div className="text-center text-muted-foreground py-4">
            No log entries available
          </div>
        </div>
      </div>
    </div>
  );
};
