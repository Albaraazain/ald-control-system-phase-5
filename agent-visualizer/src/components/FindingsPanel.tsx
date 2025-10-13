import React from 'react';
import { Agent } from '../types/Agent';

interface FindingsPanelProps {
  agent: Agent;
  projectPath: string;
}

export const FindingsPanel: React.FC<FindingsPanelProps> = ({
  agent,
  projectPath
}) => {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border">
        <h4 className="font-semibold">Findings</h4>
        <p className="text-sm text-muted-foreground">Agent insights and discoveries</p>
      </div>
      
      <div className="flex-1 p-4 overflow-auto">
        <div className="text-center text-muted-foreground py-8">
          <div className="text-2xl mb-2">🔍</div>
          <div>No findings available</div>
          <div className="text-xs mt-2">
            Agent findings will appear here when available
          </div>
        </div>
      </div>
    </div>
  );
};
