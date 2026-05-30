/**
 * semesterScheduler.js
 *
 * Given a list of courses (already in topological order, with missing_prereqs
 * and offered fields), assigns each to the earliest valid semester.
 *
 * Rules:
 *   1. All missing_prereqs must be placed in an earlier semester.
 *   2. The course must be offered in that semester type (fall/spring).
 *      If offered is empty, assume it's offered every semester.
 *   3. Total credits in a semester must not exceed maxCredits.
 *      If no slot fits within maxCredits, spill into an overflow slot.
 */

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/**
 * Convert a linear index (0, 1, 2, …) into a {type, year, name} descriptor.
 *
 * startType='fall', startYear=2025:
 *   0 → Fall 2025   1 → Spring 2026   2 → Fall 2026   …
 * startType='spring', startYear=2026:
 *   0 → Spring 2026  1 → Fall 2026  2 → Spring 2027  …
 */
export function getSemInfo(idx, startType, startYear) {
  let type, year
  if (startType === 'fall') {
    type = idx % 2 === 0 ? 'fall' : 'spring'
    year = startYear + Math.floor(idx / 2) + (idx % 2 === 1 ? 1 : 0)
  } else {
    type = idx % 2 === 0 ? 'spring' : 'fall'
    year = startYear + Math.floor(idx / 2)
  }
  return { type, year, name: `${capitalize(type)} ${year}` }
}

/**
 * Schedule an array of courses into semesters.
 *
 * @param {object[]} courses    - CourseRecommendation objects in topo order
 * @param {string}   startType  - 'fall' | 'spring'
 * @param {number}   startYear  - e.g. 2025
 * @param {number}   maxCredits - max credits per semester (default 16)
 * @returns {object[]}          - [{name, type, year, courses, credits}, …]
 */
export function scheduleCourses(courses, startType = 'fall', startYear = 2025, maxCredits = 16) {
  const semesters = []   // [{name, type, year, courses: [], credits: 0}]
  const placed   = {}    // courseId → semesterIndex

  // Fast lookup by course_id
  const courseById = {}
  courses.forEach(c => { courseById[c.course_id] = c })

  function ensureSemester(idx) {
    while (semesters.length <= idx) {
      const info = getSemInfo(semesters.length, startType, startYear)
      semesters.push({ ...info, courses: [], credits: 0 })
    }
  }

  function placeAt(course, idx) {
    ensureSemester(idx)
    semesters[idx].courses.push(course)
    semesters[idx].credits += course.credits
    placed[course.course_id] = idx
  }

  /**
   * Try to place a group of courses (main + unplaced co-reqs) together
   * into the same semester starting at minIdx.
   * Returns true on success.
   */
  function tryPlaceGroup(group, minIdx, ignoreOffering) {
    const totalCredits = group.reduce((sum, c) => sum + c.credits, 0)

    for (let idx = minIdx; idx < 40; idx++) {
      const info = getSemInfo(idx, startType, startYear)

      // All courses in the group must be offered this semester
      if (!ignoreOffering) {
        const blocked = group.some(c => c.offered?.length > 0 && !c.offered.includes(info.type))
        if (blocked) continue
      }

      ensureSemester(idx)

      if (semesters[idx].credits + totalCredits <= maxCredits) {
        group.forEach(c => placeAt(c, idx))
        return true
      }
    }
    return false
  }

  for (const course of courses) {
    // Already placed by an earlier co-req sweep — skip
    if (placed[course.course_id] !== undefined) continue

    // Earliest possible semester: one after the latest prereq placement.
    // Exception: if a prereq is listed in concurrent_prereqs, the course may
    // be placed in the SAME semester as that prereq (concurrent enrollment allowed).
    const concurrentAllowed = new Set(course.concurrent_prereqs || [])
    let minIdx = 0
    for (const prereqId of (course.missing_prereqs || [])) {
      if (placed[prereqId] !== undefined) {
        if (concurrentAllowed.has(prereqId)) {
          // Concurrent enrollment allowed — same semester is OK.
          minIdx = Math.max(minIdx, placed[prereqId])
        } else {
          // Standard prereq — must be completed in a prior semester.
          minIdx = Math.max(minIdx, placed[prereqId] + 1)
        }
      }
    }

    // Gather unplaced co-requisites that appear in our course list
    const coReqs = (course.co_requisites || [])
      .map(id => courseById[id])
      .filter(c => c && placed[c.course_id] === undefined)

    // Co-reqs' own prereqs also constrain the earliest semester
    for (const coReq of coReqs) {
      const coReqConcurrent = new Set(coReq.concurrent_prereqs || [])
      for (const prereqId of (coReq.missing_prereqs || [])) {
        if (placed[prereqId] !== undefined) {
          if (coReqConcurrent.has(prereqId)) {
            minIdx = Math.max(minIdx, placed[prereqId])
          } else {
            minIdx = Math.max(minIdx, placed[prereqId] + 1)
          }
        }
      }
    }

    const group = [course, ...coReqs]

    // Try with offering constraint, then without, then force-place
    if (!tryPlaceGroup(group, minIdx, false)) {
      if (!tryPlaceGroup(group, minIdx, true)) {
        // Force-place (overflow) — shouldn't happen often
        group.forEach(c => placeAt(c, minIdx))
      }
    }
  }

  // ── Post-processing: backfill the last 2 semesters to ≥ 12 credits ──────
  //
  // Greedy forward-packing leaves early semesters full and the last semester
  // with whatever's left (e.g. 9 credits).  We fix this by pulling courses
  // from earlier semesters into the last two, as long as doing so doesn't
  // violate any prereq or offering constraint.
  const MIN_FINAL_CREDITS = 12

  // Build a reverse-prereq map: courseId → [courseIds that depend on it]
  const dependents = {}
  for (const c of courses) {
    for (const prereqId of (c.missing_prereqs || [])) {
      if (!dependents[prereqId]) dependents[prereqId] = []
      dependents[prereqId].push(c.course_id)
    }
  }

  /**
   * True when course can be delayed from rawSrcIdx → rawDstIdx without
   * breaking any prereq chain, offering constraint, or credit cap.
   */
  function canDelayTo(course, rawDstIdx) {
    // Must not overflow the destination semester
    if (semesters[rawDstIdx].credits + course.credits > maxCredits) return false
    // Must be offered in the destination semester type (empty means any)
    const { type: dstType } = getSemInfo(rawDstIdx, startType, startYear)
    if (course.offered?.length > 0 && !course.offered.includes(dstType)) return false
    // Every course that depends on this one must be placed AFTER rawDstIdx.
    // (A dependent at rawDstIdx is only OK if this course is in its concurrent_prereqs.)
    for (const depId of (dependents[course.course_id] || [])) {
      const depIdx = placed[depId]
      if (depIdx === undefined) continue
      if (depIdx < rawDstIdx) return false   // dependent is before destination — hard violation
      if (depIdx === rawDstIdx) {
        // Same semester: allowed only when concurrent enrollment is declared
        const dep = courseById[depId]
        if (!dep?.concurrent_prereqs?.includes(course.course_id)) return false
      }
      // depIdx > rawDstIdx → dependent is after destination → fine
    }
    return true
  }

  // Identify the raw indices of the last 2 non-empty semesters.
  const nonEmptyIdxs = semesters.reduce((acc, s, i) => {
    if (s.courses.length > 0) acc.push(i)
    return acc
  }, [])

  if (nonEmptyIdxs.length >= 2) {
    // Process LAST semester first, then SECOND-TO-LAST.
    // Searching earlier-to-later source semesters (nearest first) lets us
    // naturally cascade: filling the last might pull from the second-to-last,
    // then filling the second-to-last pulls from the third-to-last, etc.
    const targets = [
      nonEmptyIdxs[nonEmptyIdxs.length - 1],
      nonEmptyIdxs[nonEmptyIdxs.length - 2],
    ]

    for (const dstIdx of targets) {
      let safety = 0
      while (semesters[dstIdx].credits < MIN_FINAL_CREDITS && safety++ < 50) {
        let moved = false
        // Search backward through earlier semesters (nearest first)
        for (let srcIdx = dstIdx - 1; srcIdx >= 0 && !moved; srcIdx--) {
          if (semesters[srcIdx].courses.length === 0) continue
          for (const course of [...semesters[srcIdx].courses]) {
            if (canDelayTo(course, dstIdx)) {
              // Move the course
              semesters[srcIdx].courses = semesters[srcIdx].courses.filter(c => c.course_id !== course.course_id)
              semesters[srcIdx].credits -= course.credits
              semesters[dstIdx].courses.push(course)
              semesters[dstIdx].credits += course.credits
              placed[course.course_id] = dstIdx
              moved = true
              break
            }
          }
        }
        if (!moved) break  // nothing more can be moved; accept current credits
      }
    }
  }

  return semesters.filter(s => s.courses.length > 0)
}

/** Parse a "fall_2025" or "spring_2026" string into {type, year}. */
export function parseSemesterKey(key) {
  const [type, year] = key.split('_')
  return { type: type.toLowerCase(), year: parseInt(year) }
}

/** Generate a list of upcoming semester options for a dropdown. */
export function upcomingSemesters(count = 6) {
  const now    = new Date()
  const year   = now.getFullYear()
  const month  = now.getMonth() // 0-indexed; Aug-Dec = fall, Jan-Jul = spring
  const type   = month >= 7 ? 'fall' : 'spring'
  const options = []
  let idx = 0
  while (options.length < count) {
    const info = getSemInfo(idx, type, year)
    options.push({ key: `${info.type}_${info.year}`, label: info.name, ...info })
    idx++
  }
  return options
}
