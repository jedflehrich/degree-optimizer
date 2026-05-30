/**
 * AuthModal — sign-in / sign-up modal.
 *
 * Props:
 *   onClose       — called when the modal should close
 *   initialMode   — 'signin' | 'signup' (default 'signin')
 */

import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function AuthModal({ onClose, initialMode = 'signin' }) {
  const [mode,     setMode]     = useState(initialMode)
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)
  const [success,  setSuccess]  = useState(null)

  const { signIn, signUp } = useAuth()

  function switchMode(next) {
    setMode(next)
    setError(null)
    setSuccess(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      if (mode === 'signin') {
        const { error } = await signIn(email, password)
        if (error) throw error
        onClose()   // success — close the modal; auth state updates automatically
      } else {
        const { error } = await signUp(email, password)
        if (error) throw error
        setSuccess('Check your email for a confirmation link, then sign in.')
      }
    } catch (err) {
      setError(err.message ?? 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // Close on overlay click (but not on modal click)
  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className="auth-overlay" onClick={handleOverlayClick}>
      <div className="auth-modal">

        <button className="auth-modal__close" onClick={onClose} aria-label="Close">
          ×
        </button>

        <h2 className="auth-modal__title">
          {mode === 'signin' ? 'Sign in' : 'Create account'}
        </h2>
        <p className="auth-modal__sub">
          Save your degree plans and access them from any device.
        </p>

        {success ? (
          <div className="auth-modal__success">
            <span>✅</span>
            <span>{success}</span>
          </div>
        ) : (
          <form className="auth-modal__form" onSubmit={handleSubmit}>
            <label className="auth-modal__label">
              Email
              <input
                type="email"
                className="auth-modal__input"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@wisc.edu"
                required
                autoFocus
                autoComplete="email"
              />
            </label>

            <label className="auth-modal__label">
              Password
              <input
                type="password"
                className="auth-modal__input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Min. 6 characters"
                required
                minLength={6}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              />
            </label>

            {error && (
              <p className="auth-modal__error">{error}</p>
            )}

            <button
              type="submit"
              className="btn btn--primary btn--lg auth-modal__submit"
              disabled={loading}
            >
              {loading
                ? <span className="btn__spinner" />
                : mode === 'signin' ? 'Sign in' : 'Create account'
              }
            </button>
          </form>
        )}

        <p className="auth-modal__toggle">
          {mode === 'signin' ? (
            <>No account?{' '}
              <button type="button" onClick={() => switchMode('signup')}>
                Create one
              </button>
            </>
          ) : (
            <>Already have one?{' '}
              <button type="button" onClick={() => switchMode('signin')}>
                Sign in
              </button>
            </>
          )}
        </p>

      </div>
    </div>
  )
}
