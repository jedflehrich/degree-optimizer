/**
 * Thin wrappers around the Degree Optimizer API.
 * All paths are relative so the Vite proxy handles the backend port.
 */

const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
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
 * Run the optimizer.
 * @param {string[]} completedCourseIds
 * @param {string[]} targetProgramIds
 */
export function optimize(completedCourseIds, targetProgramIds) {
  return request('/optimize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ completed_course_ids: completedCourseIds, target_program_ids: targetProgramIds }),
  })
}
