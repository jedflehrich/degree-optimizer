/**
 * Thin wrappers around the BuildMyDegree API.
 *
 * All paths are relative (/api/…) so the Vite proxy routes them to the
 * backend during development, and the same paths work in production when
 * the frontend and backend are served from the same origin.
 */

import { supabase } from './lib/supabase'

/** Attach the current user's JWT to outgoing requests (if signed in). */
async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` }
  }
  return {}
}

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

/** List all available programs (for the program picker). */
export function fetchPrograms() {
  return request('/programs')
}

/**
 * Search the course catalog.
 * @param {string} q - search string (matches ID, subject, name)
 */
export function searchCourses(q) {
  const params = q ? `?q=${encodeURIComponent(q)}` : ''
  return request(`/courses${params}`)
}

/**
 * Fetch the entire course catalog (no filter).
 * Used to populate alternative-course names in the requirements panel.
 */
export function fetchCatalog() {
  return request('/courses')
}

/**
 * Fetch all AP exams with UW-Madison equivalencies.
 */
export function fetchApExams() {
  return request('/ap-exams')
}

/**
 * Run the optimizer.
 * @param {string[]} completedCourseIds
 * @param {string[]} targetProgramIds
 * @param {{ genericCredit: string, credits: number }[]} apGenericCredits
 * @param {Object}  overrides   Additional request fields (e.g. one_of_overrides).
 */
export function optimize(completedCourseIds, targetProgramIds, apGenericCredits = [], overrides = {}) {
  return request('/optimize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      completed_course_ids: completedCourseIds,
      target_program_ids:   targetProgramIds,
      ap_generic_credits:   apGenericCredits.map(e => ({
        generic_credit: e.genericCredit,
        credits:        e.credits,
        exam_name:      e.examName ?? '',
      })),
      ...overrides,
    }),
  })
}

// ── Authenticated plan routes (go through FastAPI backend) ────────────────────

/**
 * List the signed-in user's saved plans (summary only).
 * @returns {Promise<object[]>}
 */
export async function fetchPlans() {
  const headers = await authHeaders()
  return request('/plans', { headers })
}

/**
 * Create a new plan.
 * @param {object} planBody  — matches PlanBody schema in plan_routes.py
 * @returns {Promise<object>}
 */
export async function createPlan(planBody) {
  const headers = await authHeaders()
  return request('/plans', {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(planBody),
  })
}

/**
 * Fully replace an existing plan.
 * @param {string} planId
 * @param {object} planBody
 */
export async function updatePlan(planId, planBody) {
  const headers = await authHeaders()
  return request(`/plans/${planId}`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(planBody),
  })
}

/**
 * Load a full plan by ID.
 * @param {string} planId
 */
export async function fetchPlan(planId) {
  const headers = await authHeaders()
  return request(`/plans/${planId}`, { headers })
}

/**
 * Delete a plan.
 * @param {string} planId
 */
export async function removePlan(planId) {
  const headers = await authHeaders()
  return fetch(`/api/plans/${planId}`, { method: 'DELETE', headers })
}
