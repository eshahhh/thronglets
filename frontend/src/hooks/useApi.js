import { useCallback } from 'react'

export function useApi(baseUrl) {
    const get = useCallback(async (path) => {
        const response = await fetch(`${baseUrl}${path}`)
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`)
        }
        return response.json()
    }, [baseUrl])

    const post = useCallback(async (path, body = null) => {
        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        }
        if (body) {
            options.body = JSON.stringify(body)
        }
        const response = await fetch(`${baseUrl}${path}`, options)
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`)
        }
        return response.json()
    }, [baseUrl])

    return { get, post }
}
