import { copy } from './translations'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// ── Token storage (localStorage, never exposed to backend logs) ───────────────
const TOKEN_KEY = 'ym-auth-token'
const USER_KEY  = 'ym-auth-user'

export function getToken() {
  return window.localStorage.getItem(TOKEN_KEY) || null
}
export function setToken(token, user) {
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token)
    window.localStorage.setItem(USER_KEY, JSON.stringify(user || {}))
  } else {
    window.localStorage.removeItem(TOKEN_KEY)
    window.localStorage.removeItem(USER_KEY)
  }
}
export function getStoredUser() {
  try { return JSON.parse(window.localStorage.getItem(USER_KEY) || 'null') }
  catch { return null }
}

// ── Core fetch helpers ─────────────────────────────────────────────────────────
export async function request(path, options = {}, lang = 'en') {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const response = await fetch(`${API}${path}`, { ...options, headers })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || copy[lang]?.retry || copy.en.retry)
  return body
}

export function postJson(path, value, lang = 'en') {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  }, lang)
}

export function deleteReq(path, lang = 'en') {
  return request(path, { method: 'DELETE' }, lang)
}

// ── Auth API calls ─────────────────────────────────────────────────────────────
export async function apiRegister(name, email, password) {
  const data = await postJson('/auth/register', { name, email, password })
  setToken(data.access_token, data.user)
  return data.user
}

export async function apiLogin(email, password) {
  const data = await postJson('/auth/login', { email, password })
  setToken(data.access_token, data.user)
  return data.user
}

export function apiLogout() {
  setToken(null)
}

// ── Saved schemes ─────────────────────────────────────────────────────────────
export function apiGetSaved() {
  return request('/user/saved-schemes')
}
export function apiSaveScheme(id) {
  return request(`/user/saved-schemes/${encodeURIComponent(id)}`, { method: 'POST' })
}
export function apiUnsaveScheme(id) {
  return deleteReq(`/user/saved-schemes/${encodeURIComponent(id)}`)
}

// ── Conversation history ───────────────────────────────────────────────────────
export function apiGetHistory() {
  return request('/user/history')
}
export function apiClearHistory() {
  return deleteReq('/user/history')
}
