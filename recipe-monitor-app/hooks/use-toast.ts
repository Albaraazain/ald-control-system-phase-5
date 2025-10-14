'use client'

import { useToastStore } from '@/lib/store/toast-store'

/**
 * Hook for accessing toast notification actions
 *
 * @returns Toast actions for showing notifications
 */
export function useToast() {
  const showToast = useToastStore((state) => state.showToast)
  const showSuccess = useToastStore((state) => state.showSuccess)
  const showError = useToastStore((state) => state.showError)
  const showWarning = useToastStore((state) => state.showWarning)
  const showInfo = useToastStore((state) => state.showInfo)

  return {
    showToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  }
}
