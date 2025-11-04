import { useState, useEffect, useCallback, useRef } from 'react'

export function useWebSocket(url) {
    const [connected, setConnected] = useState(false)
    const [lastMessage, setLastMessage] = useState(null)
    const wsRef = useRef(null)
    const reconnectTimeoutRef = useRef(null)

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return
        }

        const ws = new WebSocket(url)

        ws.onopen = () => {
            setConnected(true)
            console.log('WebSocket connected')
        }

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                setLastMessage(data)
            } catch (err) {
                console.error('Failed to parse WebSocket message:', err)
            }
        }

        ws.onclose = () => {
            setConnected(false)
            console.log('WebSocket disconnected')
            reconnectTimeoutRef.current = setTimeout(connect, 2000)
        }

        ws.onerror = (err) => {
            console.error('WebSocket error:', err)
        }

        wsRef.current = ws
    }, [url])

    useEffect(() => {
        connect()

        return () => {
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current)
            }
            if (wsRef.current) {
                wsRef.current.close()
            }
        }
    }, [connect])

    const send = useCallback((data) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data))
        }
    }, [])

    return { connected, lastMessage, send }
}
