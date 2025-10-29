'use client'

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js'
import type { ActiveTerminal, TerminalInstance } from '@/lib/types/terminal'

/**
 * Hook for fetching and subscribing to terminal status updates
 * Provides real-time visibility into terminal health for Terminal Liveness Management System
 *
 * @param machineId - UUID of the machine to monitor terminals for
 * @returns Object containing terminals array, loading state, error state, and refresh function
 */
export function useTerminalStatus(machineId: string) {
  const [terminals, setTerminals] = useState<ActiveTerminal[] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  /**
   * Fetch active terminals from the database
   * Queries the active_terminals view for current machine
   */
  const fetchTerminals = useCallback(async () => {
    try {
      const supabase = createClient()

      // Query active_terminals view for this machine
      // This view includes all active terminals with health indicators
      const { data, error: fetchError } = await supabase
        .from('active_terminals')
        .select('*')
        .eq('machine_id', machineId)
        .in('status', ['starting', 'healthy', 'degraded'])
        .order('terminal_type', { ascending: true })

      if (fetchError) {
        console.error('Failed to fetch terminals:', fetchError)
        setError(fetchError.message)
        return
      }

      setTerminals((data || []) as ActiveTerminal[])
      setError(null)
    } catch (err) {
      console.error('Error fetching terminals:', err)
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch terminals'
      setError(errorMsg)
    }
  }, [machineId])

  /**
   * Refresh function for manual updates
   * Can be called by components to force a refresh
   */
  const refresh = useCallback(async () => {
    setIsLoading(true)
    await fetchTerminals()
    setIsLoading(false)
  }, [fetchTerminals])

  useEffect(() => {
    let mounted = true
    let channel: RealtimeChannel | null = null

    /**
     * Initialize hook: fetch initial data and set up realtime subscription
     */
    async function initialize() {
      if (!mounted) return

      // Step 1: Fetch initial terminal data
      await fetchTerminals()

      if (!mounted) return
      setIsLoading(false)

      // Step 2: Subscribe to realtime updates on terminal_instances table
      const supabase = createClient()

      channel = supabase
        .channel('terminal-status-updates')
        .on(
          'postgres_changes',
          {
            event: '*', // Listen to INSERT, UPDATE, DELETE
            schema: 'public',
            table: 'terminal_instances',
            filter: `machine_id=eq.${machineId}`,
          },
          async (payload: RealtimePostgresChangesPayload<TerminalInstance>) => {
            if (!mounted) return

            // On any change to terminal_instances, refetch from active_terminals view
            // This ensures we get computed fields like health_indicator and uptime_seconds
            await fetchTerminals()
          }
        )
        .subscribe((status) => {
          if (status === 'SUBSCRIBED') {
            console.log('Terminal status subscription active')
          } else if (status === 'CHANNEL_ERROR') {
            console.error('Terminal status subscription error')
            setError('Realtime subscription failed')
          }
        })
    }

    initialize()

    // Cleanup: unsubscribe and mark as unmounted
    return () => {
      mounted = false
      if (channel) {
        const supabase = createClient()
        supabase.removeChannel(channel)
      }
    }
  }, [machineId, fetchTerminals])

  return {
    terminals,
    isLoading,
    error,
    refresh,
  }
}
