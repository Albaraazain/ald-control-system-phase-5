'use client'

import { useToasts } from '@/lib/store/toast-store';
import { useEffect, useState } from 'react';

export default function Toast() {
  const toasts = useToasts();
  const [visibleToasts, setVisibleToasts] = useState<Set<string>>(new Set());

  // Show toast with slide-up animation
  // Fixed: Removed visibleToasts from dependencies to prevent infinite loop
  useEffect(() => {
    setVisibleToasts((prev) => {
      const newSet = new Set(prev);

      // Add new toasts
      toasts.forEach((toast) => {
        newSet.add(toast.id);
      });

      // Remove toasts that are no longer in the store
      const currentIds = new Set(toasts.map((t) => t.id));
      prev.forEach((id) => {
        if (!currentIds.has(id)) {
          newSet.delete(id);
        }
      });

      return newSet;
    });
  }, [toasts]);

  // Get toast type styling
  const getToastStyles = (type: 'success' | 'error' | 'warning' | 'info') => {
    switch (type) {
      case 'success':
        return 'bg-green-100 border-green-500 text-green-900';
      case 'error':
        return 'bg-red-100 border-red-500 text-red-900';
      case 'warning':
        return 'bg-yellow-100 border-yellow-500 text-yellow-900';
      case 'info':
        return 'bg-blue-100 border-blue-500 text-blue-900';
      default:
        return 'bg-gray-100 border-gray-500 text-gray-900';
    }
  };

  // Get toast emoji
  const getToastEmoji = (type: 'success' | 'error' | 'warning' | 'info') => {
    switch (type) {
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      default:
        return '📝';
    }
  };

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => {
        const isVisible = visibleToasts.has(toast.id);

        return (
          <div
            key={toast.id}
            className={`
              transform transition-all duration-300 ease-in-out
              ${isVisible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'}
              min-w-[300px] max-w-md p-4 rounded-lg shadow-lg border-l-4
              ${getToastStyles(toast.type)}
            `}
            style={{
              animation: isVisible ? 'slideUp 0.3s ease-out' : undefined,
            }}
          >
            <div className="flex items-start gap-3">
              <span className="text-xl">{getToastEmoji(toast.type)}</span>
              <div className="flex-1">
                <p className="text-sm font-medium">{toast.message}</p>
              </div>
            </div>
          </div>
        );
      })}

      {/* Inline keyframes for slide-up animation */}
      <style jsx>{`
        @keyframes slideUp {
          from {
            transform: translateY(20px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
