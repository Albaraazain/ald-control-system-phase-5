import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration: number; // milliseconds
  createdAt: number;
}

interface ToastState {
  toasts: Toast[];

  // Actions
  showToast: (message: string, type?: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
  clearAll: () => void;

  // Convenience methods matching HTML behavior
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
  showWarning: (message: string) => void;
  showInfo: (message: string) => void;
}

// Default duration from HTML (2.5 seconds = 2500ms)
const DEFAULT_DURATION = 2500;

export const useToastStore = create<ToastState>()(
  devtools(
    (set, get) => ({
      toasts: [],

      showToast: (message, type = 'info', duration = DEFAULT_DURATION) => {
        const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const toast: Toast = {
          id,
          message,
          type,
          duration,
          createdAt: Date.now(),
        };

        set(
          (state) => ({
            toasts: [...state.toasts, toast],
          }),
          false,
          'showToast'
        );

        // Auto-remove after duration (HTML lines 282-286)
        setTimeout(() => {
          get().removeToast(id);
        }, duration);
      },

      removeToast: (id) => set(
        (state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }),
        false,
        'removeToast'
      ),

      clearAll: () => set({ toasts: [] }, false, 'clearAll'),

      // Convenience methods
      showSuccess: (message) => get().showToast(message, 'success'),
      showError: (message) => get().showToast(message, 'error'),
      showWarning: (message) => get().showToast(message, 'warning'),
      showInfo: (message) => get().showToast(message, 'info'),
    }),
    {
      name: 'toast-store',
      enabled: process.env.NODE_ENV === 'development',
    }
  )
);

// Selector hooks
export const useToasts = () => useToastStore((state) => state.toasts);
export const useShowToast = () => useToastStore((state) => state.showToast);
export const useShowSuccess = () => useToastStore((state) => state.showSuccess);
export const useShowError = () => useToastStore((state) => state.showError);
export const useShowWarning = () => useToastStore((state) => state.showWarning);
