import React, { useState } from 'react'
import { apiLogin, apiRegister } from './api'

// ─────────────────────────────────────────────────────────────────────────────
// AuthPage — Sign In / Sign Up with client-side validation
// Props:
//   onSuccess(user)  — called after successful login or registration
//   t                — translation object (uses English keys that exist in copy)
// ─────────────────────────────────────────────────────────────────────────────

function FieldError({ msg }) {
  return msg ? <span className="auth-field-error" role="alert">{msg}</span> : null
}

export function AuthPage({ onSuccess, t }) {
  const [mode, setMode] = useState('signin')       // 'signin' | 'signup'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(false)

  function switchMode(m) {
    setMode(m)
    setErrors({})
    setServerError('')
  }

  function validate() {
    const e = {}
    if (mode === 'signup') {
      if (!name.trim() || name.trim().length < 2) e.name = 'Name must be at least 2 characters.'
      if (name.trim().length > 80) e.name = 'Name is too long (max 80 characters).'
    }
    if (!email.trim()) e.email = 'Email is required.'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) e.email = 'Enter a valid email address.'
    if (!password) e.password = 'Password is required.'
    else if (mode === 'signup' && password.length < 8) e.password = 'Password must be at least 8 characters.'
    if (mode === 'signup' && password !== confirm) e.confirm = 'Passwords do not match.'
    return e
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setServerError('')
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    setErrors({})
    setLoading(true)
    try {
      const user = mode === 'signup'
        ? await apiRegister(name.trim(), email.trim(), password)
        : await apiLogin(email.trim(), password)
      onSuccess(user)
    } catch (err) {
      setServerError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="auth-page">
      <div className="auth-card">
        {/* Brand */}
        <div className="auth-brand">
          <span className="brand-mark">Y</span>
          <span>yojana<span className="brand-light">mitra</span></span>
        </div>
        <p className="auth-tagline">Government schemes made simple</p>

        {/* Mode tabs */}
        <div className="auth-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={mode === 'signin'}
            className={`auth-tab${mode === 'signin' ? ' auth-tab--active' : ''}`}
            onClick={() => switchMode('signin')}
            type="button"
          >Sign In</button>
          <button
            role="tab"
            aria-selected={mode === 'signup'}
            className={`auth-tab${mode === 'signup' ? ' auth-tab--active' : ''}`}
            onClick={() => switchMode('signup')}
            type="button"
          >Create Account</button>
        </div>

        {/* Server error */}
        {serverError && (
          <div className="auth-server-error" role="alert">{serverError}</div>
        )}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {/* Name — signup only */}
          {mode === 'signup' && (
            <div className="auth-field">
              <label htmlFor="auth-name">Full Name</label>
              <input
                id="auth-name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Your name"
                aria-describedby={errors.name ? 'auth-name-err' : undefined}
                aria-invalid={!!errors.name}
                disabled={loading}
              />
              <FieldError msg={errors.name} />
            </div>
          )}

          {/* Email */}
          <div className="auth-field">
            <label htmlFor="auth-email">Email Address</label>
            <input
              id="auth-email"
              type="email"
              autoComplete={mode === 'signup' ? 'email' : 'username'}
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              aria-invalid={!!errors.email}
              disabled={loading}
            />
            <FieldError msg={errors.email} />
          </div>

          {/* Password */}
          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder={mode === 'signup' ? 'At least 8 characters' : 'Your password'}
              aria-invalid={!!errors.password}
              disabled={loading}
            />
            <FieldError msg={errors.password} />
          </div>

          {/* Confirm password — signup only */}
          {mode === 'signup' && (
            <div className="auth-field">
              <label htmlFor="auth-confirm">Confirm Password</label>
              <input
                id="auth-confirm"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="Re-enter password"
                aria-invalid={!!errors.confirm}
                disabled={loading}
              />
              <FieldError msg={errors.confirm} />
            </div>
          )}

          <button
            className="primary-button auth-submit"
            type="submit"
            disabled={loading}
            aria-busy={loading}
          >
            {loading
              ? (mode === 'signup' ? 'Creating account…' : 'Signing in…')
              : (mode === 'signup' ? 'Create Account' : 'Sign In')}
          </button>
        </form>

        <p className="auth-switch-hint">
          {mode === 'signin'
            ? <>Don&apos;t have an account? <button type="button" className="auth-link-btn" onClick={() => switchMode('signup')}>Create one</button></>
            : <>Already have an account? <button type="button" className="auth-link-btn" onClick={() => switchMode('signin')}>Sign in</button></>
          }
        </p>

        <p className="auth-privacy-note">
          Your account is used only to save your preferences within this app. We do not share your data.
        </p>
      </div>
    </section>
  )
}
