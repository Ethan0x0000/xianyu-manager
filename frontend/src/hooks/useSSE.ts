import { useEffect, useRef } from 'react'

const MAX_RECONNECT_ATTEMPTS = 5

export function useSSE(url: string, onEvent: (event: MessageEvent<string>) => void) {
  const onEventRef = useRef(onEvent)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!url || typeof EventSource === 'undefined') {
      return
    }

    let eventSource: EventSource | null = null
    let reconnectTimer: number | null = null
    let closed = false
    let reconnectAttempts = 0

    const clearReconnectTimer = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    const connect = () => {
      if (closed || reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        return
      }

      eventSource = new EventSource(url)
      eventSource.onmessage = (event) => {
        reconnectAttempts = 0
        onEventRef.current(event)
      }
      eventSource.onerror = () => {
        eventSource?.close()

        if (closed || reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
          return
        }

        reconnectAttempts += 1
        const delay = 1000 * 2 ** (reconnectAttempts - 1)

        clearReconnectTimer()
        reconnectTimer = window.setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      closed = true
      clearReconnectTimer()
      eventSource?.close()
    }
  }, [url])
}
