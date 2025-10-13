import { ProjectScanner } from '../ProjectScanner';
import { promises as fs } from 'fs';
import * as path from 'path';

// Mock fs module
jest.mock('fs');
const mockedFs = fs as jest.Mocked<typeof fs>;

describe('ProjectScanner', () => {
  let scanner: ProjectScanner;

  beforeEach(() => {
    scanner = ProjectScanner.getInstance();
    scanner.clearCache();
    jest.clearAllMocks();
  });

  describe('getInstance', () => {
    it('should return the same instance (singleton pattern)', () => {
      const instance1 = ProjectScanner.getInstance();
      const instance2 = ProjectScanner.getInstance();
      expect(instance1).toBe(instance2);
    });
  });

  describe('scanDirectory', () => {
    it('should find projects with .agent-workspace directories', async () => {
      // Mock directory structure
      mockedFs.readdir.mockImplementation(async (dirPath: any, options?: any) => {
        if (dirPath === '/test/root') {
          return [
            { name: 'project1', isDirectory: () => true },
            { name: 'project2', isDirectory: () => true },
            { name: 'file.txt', isDirectory: () => false }
          ] as any;
        }
        if (dirPath === '/test/root/project1') {
          return [
            { name: '.agent-workspace', isDirectory: () => true },
            { name: 'src', isDirectory: () => true }
          ] as any;
        }
        if (dirPath === '/test/root/project2') {
          return [
            { name: 'src', isDirectory: () => true }
          ] as any;
        }
        if (dirPath === '/test/root/project1/.agent-workspace') {
          return [
            { name: 'AGENT_REGISTRY.json', isDirectory: () => false },
            { name: 'TASK-001', isDirectory: () => true }
          ] as any;
        }
        return [];
      });

      mockedFs.stat.mockResolvedValue({
        mtime: new Date('2025-10-10T20:00:00Z'),
        isDirectory: () => true
      } as any);

      const projects = await scanner.scanDirectory('/test/root', 2);

      expect(projects).toHaveLength(1);
      expect(projects[0].name).toBe('project1');
      expect(projects[0].path).toBe('/test/root/project1');
      expect(projects[0].valid).toBe(true);
    });

    it('should handle directories without permissions gracefully', async () => {
      mockedFs.readdir.mockRejectedValue(new Error('Permission denied'));
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

      const projects = await scanner.scanDirectory('/restricted', 2);

      expect(projects).toHaveLength(0);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Cannot scan directory /restricted:',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    it('should respect max depth limit', async () => {
      const scanSpy = jest.spyOn(scanner as any, 'scanDirectoryRecursive');

      mockedFs.readdir.mockResolvedValue([]);

      await scanner.scanDirectory('/test', 0);

      // Should only call once for the root directory
      expect(scanSpy).toHaveBeenCalledTimes(1);
    });
  });

  describe('analyzeProject', () => {
    it('should analyze a valid project with .agent-workspace', async () => {
      mockedFs.stat.mockResolvedValue({
        mtime: new Date('2025-10-10T20:00:00Z')
      } as any);

      mockedFs.readdir.mockResolvedValue([
        { name: 'TASK-001', isDirectory: () => true },
        { name: 'TASK-002', isDirectory: () => true }
      ] as any);

      const result = await scanner.analyzeProject('/test/project');

      expect(result.name).toBe('project');
      expect(result.path).toBe('/test/project');
      expect(result.valid).toBe(true);
      expect(result.task_count).toBe(2);
    });

    it('should handle invalid project paths', async () => {
      mockedFs.stat.mockRejectedValue(new Error('Path not found'));
      mockedFs.readdir.mockRejectedValue(new Error('Path not found'));

      const result = await scanner.analyzeProject('/invalid/path');

      expect(result.valid).toBe(false);
      expect(result.error).toBe('Path not found');
    });
  });

  describe('loadAgentRegistry', () => {
    it('should load agent registry from main workspace', async () => {
      const mockRegistry = {
        task_id: 'test-task',
        description: 'Test task',
        created_at: '2025-10-10T20:00:00Z',
        agents: [
          {
            id: 'agent-1',
            type: 'worker',
            status: 'running',
            progress: 50,
            started_at: '2025-10-10T20:00:00Z',
            last_update: '2025-10-10T20:30:00Z'
          }
        ]
      };

      mockedFs.readFile.mockResolvedValue(JSON.stringify(mockRegistry));

      const result = await scanner.loadAgentRegistry('/test/project');

      expect(result).toEqual(mockRegistry);
      expect(mockedFs.readFile).toHaveBeenCalledWith(
        '/test/project/.agent-workspace/AGENT_REGISTRY.json',
        'utf-8'
      );
    });

    it('should fallback to most recent task registry', async () => {
      // First call fails (main registry not found)
      mockedFs.readFile.mockRejectedValueOnce(new Error('File not found'));

      // Mock task directories
      mockedFs.readdir.mockResolvedValue([
        { name: 'TASK-001', isDirectory: () => true },
        { name: 'TASK-002', isDirectory: () => true }
      ] as any);

      // Mock stat calls for task directories
      mockedFs.stat
        .mockResolvedValueOnce({ mtime: new Date('2025-10-10T19:00:00Z') } as any)
        .mockResolvedValueOnce({ mtime: new Date('2025-10-10T20:00:00Z') } as any);

      // Mock successful registry read from most recent task
      const mockRegistry = {
        task_id: 'task-002',
        description: 'Latest task',
        created_at: '2025-10-10T20:00:00Z',
        agents: []
      };

      mockedFs.readFile.mockResolvedValueOnce(JSON.stringify(mockRegistry));

      const result = await scanner.loadAgentRegistry('/test/project');

      expect(result).toEqual(mockRegistry);
    });

    it('should return null when no registry found', async () => {
      mockedFs.readFile.mockRejectedValue(new Error('File not found'));
      mockedFs.readdir.mockResolvedValue([]);

      const result = await scanner.loadAgentRegistry('/test/project');

      expect(result).toBeNull();
    });
  });

  describe('getWorkspaceStructure', () => {
    it('should analyze workspace structure correctly', async () => {
      mockedFs.readdir
        .mockResolvedValueOnce([
          { name: 'AGENT_REGISTRY.json', isDirectory: () => false },
          { name: 'findings', isDirectory: () => true },
          { name: 'logs', isDirectory: () => true },
          { name: 'TASK-001', isDirectory: () => true }
        ] as any)
        .mockResolvedValueOnce([
          { name: 'TASK-001', isDirectory: () => true }
        ] as any);

      // Mock task registry file
      mockedFs.readFile.mockResolvedValue(JSON.stringify({
        task_id: 'task-001',
        description: 'Test task',
        created_at: '2025-10-10T20:00:00Z',
        agents: [{ id: 'agent-1', status: 'running' }]
      }));

      mockedFs.stat.mockResolvedValue({
        mtime: new Date('2025-10-10T20:00:00Z')
      } as any);

      // Mock file existence check
      (scanner as any).fileExists = jest.fn().mockResolvedValue(true);

      const result = await scanner.getWorkspaceStructure('/test/.agent-workspace');

      expect(result.has_agent_workspace).toBe(true);
      expect(result.has_registry).toBe(true);
      expect(result.has_findings).toBe(true);
      expect(result.has_logs).toBe(true);
      expect(result.task_directories).toEqual(['TASK-001']);
    });
  });

  describe('watchProject', () => {
    it('should create file watcher for project', () => {
      const mockCallback = jest.fn();
      const mockWatcher = { close: jest.fn() };

      // Mock fs.watch through the mocked fs module
      jest.doMock('fs', () => ({
        watch: jest.fn(() => mockWatcher),
        promises: mockedFs
      }));

      const watcher = scanner.watchProject('/test/project', mockCallback);

      expect(watcher).toBe(mockWatcher);
    });
  });

  describe('cache management', () => {
    it('should cache discovered projects', async () => {
      mockedFs.readdir.mockResolvedValue([]);

      await scanner.scanDirectory('/test', 1);
      const cachedProjects = scanner.getCachedProjects();

      expect(Array.isArray(cachedProjects)).toBe(true);
    });

    it('should clear cache when requested', async () => {
      mockedFs.readdir.mockResolvedValue([]);

      await scanner.scanDirectory('/test', 1);
      scanner.clearCache();
      const cachedProjects = scanner.getCachedProjects();

      expect(cachedProjects).toHaveLength(0);
    });
  });
});
