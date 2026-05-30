/**
 * Supabase browser client (anon key only — safe for the frontend).
 *
 * Reads VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY from the environment.
 * If either is missing the app still runs — auth and plan save/load are
 * just disabled with a console warning.
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl     = import.meta.env.VITE_SUPABASE_URL     ?? ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''

const configured = Boolean(supabaseUrl && supabaseAnonKey)

if (!configured) {
  console.warn(
    '[BuildMyDegree] VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY is missing from .env.\n' +
    'Auth and plan save/load are disabled until these are set.'
  )
}

// A no-op stub so the rest of the app never has to null-check `supabase`.
const _stub = {
  auth: {
    getSession:        () => Promise.resolve({ data: { session: null }, error: null }),
    getUser:           () => Promise.resolve({ data: { user: null },    error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
    signInWithPassword:() => Promise.resolve({ error: { message: 'Supabase not configured.' } }),
    signUp:            () => Promise.resolve({ error: { message: 'Supabase not configured.' } }),
    signOut:           () => Promise.resolve({ error: null }),
  },
  from: () => {
    const err = { message: 'Supabase not configured.' }
    const chain = {
      select:  () => chain,
      eq:      () => chain,
      order:   () => chain,
      single:  () => Promise.resolve({ data: null, error: err }),
      upsert:  () => chain,
      delete:  () => chain,
      then:    (resolve) => resolve({ data: null, error: err }),
    }
    return chain
  },
}

export const supabase = configured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : _stub
