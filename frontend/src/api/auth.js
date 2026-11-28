import { apiFetch, apiRequest, readApiError } from './http.js'

const publicRequest = (path, data) => apiRequest('/auth' + path, 'POST', data, { authenticated: false })

export const authApi = {
  async session() {
    const response = await apiFetch('/auth/session', {}, { authenticated: false })
    if (response.status === 401) return null
    if (!response.ok) throw await readApiError(response, '无法检查登录状态')
    return response.json()
  },
  register: (username, password) => publicRequest('/register', { username, password }),
  login: (username, password) => publicRequest('/login', { username, password }),
  logout: () => apiRequest('/auth/logout', 'POST'),
}
