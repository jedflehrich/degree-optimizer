/**
 * useProfile
 * Persists the student's setup choices to localStorage so they don't have
 * to re-enter everything on every visit.
 *
 * Stored shape:
 * {
 *   name:             string          — optional display name
 *   selectedPrograms: string[]        — program IDs
 *   manualCourses:    string[]        — course IDs added via search
 *   apEntries:        ApEntry[]       — AP exam selections with resolved courses
 *   savedAt:          ISO string
 * }
 */

import { useState, useEffect, useRef } from 'react'

const KEY     = 'degree_optimizer_profile'
const VERSION = 1   // bump this to wipe stale data on schema changes

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed._version !== VERSION) return null   // schema changed — start fresh
    return parsed
  } catch {
    return null
  }
}

function save(data) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...data, _version: VERSION, savedAt: new Date().toISOString() }))
  } catch {
    // Quota exceeded or private browsing — silently ignore
  }
}

export function useProfile() {
  const initial = load()

  const [name,             setName]             = useState(initial?.name             ?? '')
  const [selectedPrograms, setSelectedPrograms] = useState(initial?.selectedPrograms ?? [])
  const [manualCourses,    setManualCourses]    = useState(initial?.manualCourses    ?? [])
  const [apEntries,        setApEntries]        = useState(initial?.apEntries        ?? [])
  const [savedAt,          setSavedAt]          = useState(initial?.savedAt          ?? null)

  // Auto-save whenever any field changes.
  // Use a ref to skip the very first render (avoids overwriting on mount).
  const isFirstRender = useRef(true)
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return }
    const ts = new Date().toISOString()
    save({ name, selectedPrograms, manualCourses, apEntries })
    setSavedAt(ts)
  }, [name, selectedPrograms, manualCourses, apEntries])

  function clearProfile() {
    localStorage.removeItem(KEY)
    setName('')
    setSelectedPrograms([])
    setManualCourses([])
    setApEntries([])
    setSavedAt(null)
  }

  const isReturning = Boolean(initial && (initial.selectedPrograms?.length || initial.manualCourses?.length || initial.apEntries?.length))

  return {
    name, setName,
    selectedPrograms, setSelectedPrograms,
    manualCourses, setManualCourses,
    apEntries, setApEntries,
    savedAt,
    isReturning,
    clearProfile,
  }
}

/** Format a savedAt ISO string into a human-readable "X ago" label. */
export function timeAgo(iso) {
  if (!iso) return null
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 10)  return 'just now'
  if (diff < 60)  return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
