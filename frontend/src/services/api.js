let csrfToken = ''

export async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method) && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }
  const response = await fetch(path, {
    ...options,
    credentials: 'include',
    headers,
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.error || 'The request could not be completed.')
  if (body.csrf_token) csrfToken = body.csrf_token
  return body
}
