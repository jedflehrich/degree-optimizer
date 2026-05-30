/**
 * AuthContext — global auth state for BuildMyDegree.
 *
 * Wraps the app in <AuthProvider> (see main.jsx).
 * Components access auth state via the useAuth() hook.
 *
 * Exposed values:
 *   user     — Supabase User object (null if signed out)
 *   session  — Supabase Session (null if signed out)
 *   loading  — true during the initial session lookup
 *   signIn(email, password)  — returns { error }
 *   signUp(email, password)  — returns { error }
 *   signOut()
 */

import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null)
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get the existing session (stored in localStorage by the Supabase client).
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for login, logout, and token-refresh events.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const value = {
    user,
    session,
    loading,
    signIn:  (email, password) => supabase.auth.signInWithPassword({ email, password }),
    signUp:  (email, password) => supabase.auth.signUp({ email, password }),
    signOut: ()                => supabase.auth.signOut(),
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

/** Access auth state from any component inside <AuthProvider>. */
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>.')
  return ctx
}
