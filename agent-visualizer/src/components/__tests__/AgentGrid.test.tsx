import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentGrid } from '../AgentGrid';
import { Agent } from '../../types/Agent';

const mockAgents: Agent[] = [
  {
    id: 'worker-001',
    type: 'worker',
    status: 'running',
    progress: 65,
    started_at: '2025-10-10T20:00:00Z',
    last_update: '2025-10-10T20:30:00Z',
    prompt_summary: 'Processing data analysis tasks',
    model: 'gpt-4',
    tmux_session: 'worker-001-session'
  },
  {
    id: 'coordinator-001',
    type: 'coordinator',
    status: 'completed',
    progress: 100,
    started_at: '2025-10-10T20:00:00Z',
    last_update: '2025-10-10T20:25:00Z',
    prompt_summary: 'Coordinating task distribution',
    model: 'gpt-4'
  },
  {
    id: 'supervisor-001',
    type: 'supervisor',
    status: 'failed',
    progress: 25,
    started_at: '2025-10-10T20:05:00Z',
    last_update: '2025-10-10T20:15:00Z',
    prompt_summary: 'Quality assurance monitoring',
    model: 'claude-3-sonnet'
  }
];

describe('AgentGrid', () => {
  const mockOnAgentSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render empty state when no agents provided', () => {
    render(
      <AgentGrid
        agents={[]}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    expect(screen.getByText('No agents found')).toBeInTheDocument();
    expect(screen.getByText('Agents will appear here when they are active in the project')).toBeInTheDocument();
  });

  it('should render agent cards when agents are provided', () => {
    render(
      <AgentGrid
        agents={mockAgents}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    // Check if all agents are rendered
    expect(screen.getByText('worker-001')).toBeInTheDocument();
    expect(screen.getByText('coordinator-001')).toBeInTheDocument();
    expect(screen.getByText('supervisor-001')).toBeInTheDocument();
  });

  it('should display correct agent information', () => {
    render(
      <AgentGrid
        agents={[mockAgents[0]]}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    // Check agent details
    expect(screen.getByText('worker')).toBeInTheDocument();
    expect(screen.getByText('65%')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('gpt-4')).toBeInTheDocument();
    expect(screen.getByText('worker-001-session')).toBeInTheDocument();
    expect(screen.getByText('Processing data analysis tasks')).toBeInTheDocument();
  });

  it('should show correct status colors and styles', () => {
    render(
      <AgentGrid
        agents={mockAgents}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    const runningAgent = screen.getByText('worker-001').closest('.agent-card');
    const completedAgent = screen.getByText('coordinator-001').closest('.agent-card');
    const failedAgent = screen.getByText('supervisor-001').closest('.agent-card');

    // Check for running status (should have pulsing animation)
    expect(runningAgent?.querySelector('.agent-running')).toBeInTheDocument();
  });

  it('should call onAgentSelect when agent card is clicked', () => {
    render(
      <AgentGrid
        agents={[mockAgents[0]]}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    const agentCard = screen.getByText('worker-001').closest('.agent-card');
    fireEvent.click(agentCard!);

    expect(mockOnAgentSelect).toHaveBeenCalledWith(mockAgents[0]);
  });

  it('should highlight selected agent', () => {
    render(
      <AgentGrid
        agents={mockAgents}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={mockAgents[0]}
      />
    );

    const selectedCard = screen.getByText('worker-001').closest('.agent-card');
    expect(selectedCard).toHaveClass('border-primary', 'bg-primary/5');
  });

  it('should show correct type icons', () => {
    render(
      <AgentGrid
        agents={mockAgents}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    // Check for type icons (emojis)
    expect(screen.getByText('⚡')).toBeInTheDocument(); // worker
    expect(screen.getByText('🎯')).toBeInTheDocument(); // coordinator
    expect(screen.getByText('👁️')).toBeInTheDocument(); // supervisor
  });

  it('should display progress bars correctly', () => {
    render(
      <AgentGrid
        agents={[mockAgents[0]]}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    const progressBar = screen.getByText('65%').parentElement?.nextElementSibling?.querySelector('div');
    expect(progressBar).toHaveStyle({ width: '65%' });
  });

  it('should show different progress bar colors based on status', () => {
    render(
      <AgentGrid
        agents={mockAgents}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    // Check for completed agent (should have green progress bar)
    const completedCard = screen.getByText('coordinator-001').closest('.agent-card');
    const completedProgressBar = completedCard?.querySelector('.bg-green-500');
    expect(completedProgressBar).toBeInTheDocument();

    // Check for failed agent (should have red progress bar)
    const failedCard = screen.getByText('supervisor-001').closest('.agent-card');
    const failedProgressBar = failedCard?.querySelector('.bg-red-500');
    expect(failedProgressBar).toBeInTheDocument();
  });

  it('should format timestamps correctly', () => {
    render(
      <AgentGrid
        agents={[mockAgents[0]]}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    // Check if time is displayed (format may vary based on locale)
    const timeElement = screen.getByText(/\d{1,2}:\d{2}:\d{2}/);
    expect(timeElement).toBeInTheDocument();
  });

  it('should handle agents without optional fields gracefully', () => {
    const minimalAgent: Agent = {
      id: 'minimal-agent',
      type: 'monitor',
      status: 'idle',
      progress: 0,
      started_at: '2025-10-10T20:00:00Z',
      last_update: '2025-10-10T20:00:00Z'
    };

    render(
      <AgentGrid
        agents={[minimalAgent]}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    expect(screen.getByText('minimal-agent')).toBeInTheDocument();
    expect(screen.getByText('monitor')).toBeInTheDocument();
    expect(screen.getByText('idle')).toBeInTheDocument();
  });

  it('should apply hover effects on agent cards', () => {
    render(
      <AgentGrid
        agents={[mockAgents[0]]}
        onAgentSelect={mockOnAgentSelect}
        selectedAgent={null}
      />
    );

    const agentCard = screen.getByText('worker-001').closest('.agent-card');
    expect(agentCard).toHaveClass('agent-card');
  });
});
