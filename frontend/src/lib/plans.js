/**
 * Plan persistence helpers — direct Supabase JS client calls.
 *
 * Row Level Security on the `plans` table ensures users can only access
 * their own rows. The `user_id` column is set server-side from auth.uid()
 * at insert time, so RLS correctly gates all reads and writes.
 */

import { supabase } from './supabase'

/**
 * Create or update a plan.
 *
 * - Pass `id` to UPDATE an existing plan.
 * - Omit `id` to INSERT a new plan (Supabase generates the UUID).
 *
 * @param {object} plan
 * @param {string}   [plan.id]
 * @param {string}   plan.name
 * @param {string[]} plan.targetProgramIds
 * @param {string[]} plan.completedCourseIds
 * @param {any[]}    plan.apCredits
 * @param {string[]} [plan.selectedCourseIds]
 * @param {any}      [plan.semesterPlan]
 * @param {string}   [plan.startSemester]
 * @param {number}   [plan.maxCredits]
 * @returns {Promise<object>} The saved plan row.
 */
export async function upsertPlan({
  id,
  name,
  targetProgramIds,
  completedCourseIds,
  apCredits,
  selectedCourseIds = [],
  semesterPlan      = null,
  startSemester     = 'fall_2025',
  maxCredits        = 16,
}) {
  // Include user_id so the RLS policy (auth.uid() = user_id) passes on INSERT.
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Not signed in.')

  const payload = {
    ...(id ? { id } : {}),
    user_id:              user.id,
    name:                 name || 'My Plan',
    target_program_ids:   targetProgramIds   ?? [],
    completed_course_ids: completedCourseIds ?? [],
    ap_credits:           apCredits          ?? [],
    selected_course_ids:  selectedCourseIds,
    semester_plan:        semesterPlan,
    start_semester:       startSemester,
    max_credits:          maxCredits,
  }

  const { data, error } = await supabase
    .from('plans')
    .upsert(payload)
    .select()
    .single()

  if (error) throw error
  return data
}

/**
 * List a summary of all plans belonging to the logged-in user, newest first.
 * @returns {Promise<object[]>}
 */
export async function listPlans() {
  const { data, error } = await supabase
    .from('plans')
    .select('id, name, target_program_ids, updated_at')
    .order('updated_at', { ascending: false })

  if (error) throw error
  return data ?? []
}

/**
 * Load a full plan by ID.
 * @param {string} id
 * @returns {Promise<object>}
 */
export async function loadPlan(id) {
  const { data, error } = await supabase
    .from('plans')
    .select('*')
    .eq('id', id)
    .single()

  if (error) throw error
  return data
}

/**
 * Permanently delete a plan.
 * @param {string} id
 */
export async function deletePlan(id) {
  const { error } = await supabase.from('plans').delete().eq('id', id)
  if (error) throw error
}
