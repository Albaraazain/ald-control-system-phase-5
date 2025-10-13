import '@testing-library/jest-dom';

// Mock process.env for tests
Object.defineProperty(process, 'env', {
  value: {
    HOME: '/mock/home',
    USERPROFILE: '/mock/home',
    NODE_ENV: 'test'
  }
});

// Mock fs module for testing
jest.mock('fs', () => ({
  promises: {
    readdir: jest.fn(),
    readFile: jest.fn(),
    stat: jest.fn(),
    access: jest.fn()
  },
  watch: jest.fn(() => ({
    close: jest.fn()
  }))
}));

// Mock Electron APIs
Object.defineProperty(window, 'electronAPI', {
  value: {
    getAppVersion: () => Promise.resolve('1.0.0'),
    openDirectoryDialog: () => Promise.resolve(['/mock/path']),
    showNotification: jest.fn(),
    onMenuAction: jest.fn()
  }
});

// Mock console methods for cleaner test output
const originalError = console.error;
const originalWarn = console.warn;

beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' && 
      args[0].includes('Warning: ReactDOM.render is deprecated')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
  
  console.warn = (...args) => {
    if (
      typeof args[0] === 'string' && 
      (args[0].includes('componentWillReceiveProps') || 
       args[0].includes('componentWillUpdate'))
    ) {
      return;
    }
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});
