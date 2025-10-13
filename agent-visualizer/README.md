# Agent Visualizer

A desktop application built with Electron and React to visualize and monitor agents, their progress, and findings across multiple projects with `.agent-workspace` directories.

## Features

- **Multi-Project Support**: Automatically discovers and manages multiple projects with `.agent-workspace` directories
- **Real-time Agent Monitoring**: View agent status, progress, and activity in real-time
- **Interactive Dashboard**: Grid and timeline views for agent visualization
- **Project Overview**: Summary statistics and progress tracking per project
- **Agent Details**: Detailed view of individual agents with findings and logs
- **Dark/Light Theme**: Toggle between themes for better visibility
- **File System Integration**: Watches for changes in agent workspace directories

## Installation

1. Clone or create the agent-visualizer directory
2. Install dependencies:
   ```bash
   npm install
   ```

## Development

Start the development server:
```bash
npm start
```

## Build

Create a production build:
```bash
npm run make
```

## Usage

### Project Discovery

The application automatically scans common directories for projects containing `.agent-workspace` folders:
- Home directory
- Documents
- Projects
- Development
- Code

### Agent Workspace Structure

The visualizer expects the following structure in each project:

```
your-project/
├── .agent-workspace/
│   ├── AGENT_REGISTRY.json          # Main agent registry
│   ├── TASK-[timestamp]/            # Task-specific directories
│   │   ├── AGENT_REGISTRY.json      # Task agent registry
│   │   ├── findings/                # Agent findings
│   │   ├── logs/                    # Agent logs
│   │   └── progress/                # Progress tracking
│   └── ...
```

### Agent Registry Format

The `AGENT_REGISTRY.json` files should contain:

```json
{
  "task_id": "unique-task-id",
  "description": "Task description",
  "created_at": "2025-01-01T00:00:00Z",
  "agents": [
    {
      "id": "agent-1",
      "type": "worker",
      "status": "running",
      "progress": 45,
      "started_at": "2025-01-01T00:00:00Z",
      "last_update": "2025-01-01T00:30:00Z",
      "prompt_summary": "Agent task description",
      "model": "gpt-4",
      "tmux_session": "session-name"
    }
  ]
}
```

### Supported Agent Types

- **Worker**: General task execution agents
- **Coordinator**: Task coordination and management
- **Supervisor**: Oversight and monitoring agents
- **Monitor**: System and performance monitoring

### Agent Status Values

- **running**: Currently active
- **completed**: Task finished successfully
- **failed**: Task encountered an error
- **paused**: Temporarily halted
- **idle**: Waiting for work

## Interface Overview

### Project Sidebar
- Lists all discovered projects
- Shows project status and recent activity
- Quick project switching

### Main Dashboard
- Project overview with statistics
- Agent grid/timeline view toggle
- Real-time progress monitoring

### Agent Details Panel
- Individual agent information
- Findings and discoveries
- Live log streaming

## Configuration

The application supports various configuration options:

- **Refresh Interval**: How often to update agent data
- **Auto-scroll Logs**: Automatically scroll to latest log entries
- **Debug Logs**: Show/hide debug level messages
- **Notifications**: Desktop notifications for agent events
- **Theme**: Light/dark/auto theme selection

## Architecture

### Frontend (React)
- **App.tsx**: Main application component
- **Components**: Modular UI components for different views
- **Store**: Zustand-based state management
- **Types**: TypeScript interfaces for type safety

### Backend Services
- **ProjectScanner**: Discovers and analyzes projects
- **File Watchers**: Monitor workspace changes
- **Data Processing**: Parse and structure agent data

### Electron Integration
- **Main Process**: Application lifecycle and window management
- **Renderer Process**: React application and UI
- **IPC**: Communication between main and renderer processes

## Development Notes

### Key Components

1. **ProjectScanner.ts**: Core service for discovering and analyzing projects
2. **App.tsx**: Main React application component
3. **AgentGrid.tsx**: Grid view for agent visualization
4. **ProjectSidebar.tsx**: Project navigation and management

### State Management

Uses Zustand for lightweight state management:
- Project list and selection
- Agent data and status
- UI preferences and settings

### Styling

Uses Tailwind CSS with custom design system:
- Dark/light theme support
- Responsive design
- Custom animations for agent status

## Troubleshooting

### No Projects Found
- Ensure projects have `.agent-workspace` directories
- Check directory permissions
- Verify agent registry files exist

### Agents Not Updating
- Check file watcher permissions
- Verify agent registry format
- Ensure timestamps are current

### Performance Issues
- Limit log retention period
- Reduce refresh interval
- Check for large agent workspace directories

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details
