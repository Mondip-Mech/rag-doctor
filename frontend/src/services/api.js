/**
 * RAG Doctor API Service
 *
 * Centralizes communication between the React frontend
 * and the existing FastAPI backend.
 */

/**
 * Sends an HTTP request and processes its JSON response.
 */
async function requestJson(url, options = {}) {
    let response

    // Handle network connectivity errors.
    try {
        response = await fetch(url, options)
    } catch {
        throw new Error(
            'Unable to connect to the backend. ' +
            'Please check whether FastAPI is running on port 8000.',
        )
    }

    // Parse the response safely.
    const contentType = response.headers.get('content-type') || ''

    let data

    if (contentType.includes('application/json')) {
        data = await response.json().catch(() => null)
    } else {
        data = await response.text().catch(() => '')
    }

    // Handle HTTP errors.
    if (!response.ok) {
        const detail = data?.detail

        let message = 'An unexpected API error occurred.'

        if (typeof detail === 'string') {
            message = detail
        } else if (Array.isArray(detail)) {
            message = detail
                .map((item) => item.msg || JSON.stringify(item))
                .join('; ')
        }

        const error = new Error(
            `${message} (HTTP ${response.status})`,
        )

        error.status = response.status

        throw error
    }

    return data
}

/**
 * Checks whether the FastAPI backend is available.
 */
export function checkBackendHealth() {
    return requestJson('/health')
}

/**
 * Executes a RAG diagnostic workflow.
 *
 * @param {Object} payload - DiagnosticRequest payload.
 * @returns {Promise<Object>} DiagnosticAPIResponse.
 */
export function runDiagnostic(payload) {
    return requestJson('/api/v1/diagnostics', {
        method: 'POST',

        headers: {
            'Content-Type': 'application/json',
        },

        body: JSON.stringify(payload),
    })
}