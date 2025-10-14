'use client'

import { useLogs } from '@/lib/store/dashboard-store';
import { useEffect, useRef } from 'react';

export default function LogPanel() {
  // Get logs from store (last 20 entries)
  const logs = useLogs();
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new entries (HTML line 303)
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // Format timestamp as HH:MM:SS (HTML line 291)
  const formatTime = (timestamp: Date): string => {
    const hours = timestamp.getHours().toString().padStart(2, '0');
    const minutes = timestamp.getMinutes().toString().padStart(2, '0');
    const seconds = timestamp.getSeconds().toString().padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
  };

  return (
    <div className="border border-gray-300 p-4 bg-white">
      <h2 className="text-lg font-bold mb-4">Execution Log</h2>

      {/* Log entries container - HTML lines 166-169, 237-240, 295-304 */}
      <div
        className="h-[260px] overflow-auto font-mono text-xs text-gray-700 space-y-1"
        style={{ fontFamily: 'monospace' }}
      >
        {logs.length === 0 ? (
          <div className="text-gray-400">No log entries yet</div>
        ) : (
          logs.map((log) => (
            <div
              key={log.id}
              className="border-b border-dotted border-gray-300 pb-1 mb-1 last:border-b-0"
            >
              {/* Log entry format: "[TIME] - [MESSAGE]" (HTML line 300) */}
              <span className="text-gray-500">[{formatTime(log.timestamp)}]</span>
              {' - '}
              <span>{log.message}</span>
            </div>
          ))
        )}
        {/* Auto-scroll anchor */}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
