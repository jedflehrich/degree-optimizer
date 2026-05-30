import { useState, useMemo, useEffect } from 'react'

/**
 * RequirementsPanel — DARS-style checklist
 *
 * Shows every requirement category for each program:
 *   ✓ Satisfied   → compact green row, collapsed by default, click to see which courses.
 *   ⚠ Unsatisfied → amber row expanded by default, showing selection UI for what's still needed.
 *
 * Props:
 *   result      — OptimizeResponse from the API
 *   catalog     — Full course catalog from GET /api/courses (for alternative names)
 *   hasIEandDS  — true when both IE and DS programs are selected (L&S waiver)
 *   onConfirm   — callback(finalCourses: CourseRecommendation[]) when user
 *                 clicks "Build Semester Plan"
 */

// Group IDs that are waived for IE + DS double majors (L&S distribution requirements).
const LS_WAIVED_PREFIX = 'ls_bs'

export default function RequirementsPanel({ result, catalog = [], hasIEandDS = false, onConfirm, onSelectionsChange, importedCourseIds = null, onPickOneOf = null, oneOfChoices = {} }) {
  // Build a lookup: courseId → course details.
  // Priority: (1) catalog entries for names/credits, then (2) optimizer's richer recommendation data.
  const courseMap = useMemo(() => {
    const m = {}
    catalog.forEach(c => {
      m[c.id] = {
        course_id: c.id,
        name: c.name,
        credits: c.credits,
        offered: c.offered || [],
        prerequisites: c.prerequisites || [],
        overlap_score: 0,
        can_take_now: true,
        missing_prereqs: [],
        co_requisites: c.co_requisites || [],
        concurrent_prereqs: c.concurrent_prereqs || [],
        is_prereq_filler: false,
        satisfies_groups: [],
      }
    })
    // Preserve catalog prerequisites when overriding with optimizer data.
    result.recommended_courses.forEach(c => { m[c.course_id] = { prerequisites: m[c.course_id]?.prerequisites || [], ...c } })
    result.prereq_only_courses.forEach(c => { m[c.course_id] = { prerequisites: m[c.course_id]?.prerequisites || [], ...c } })
    return m
  }, [result, catalog])

  // Map every group_id (at any depth) → program_id.
  // Used to compute how many programs a course actually overlaps (vs. raw group count).
  const groupToProgram = useMemo(() => {
    const map = {}
    function traverse(gs, programId) {
      map[gs.group_id] = programId
      for (const ss of gs.sub_statuses || []) traverse(ss, programId)
    }
    for (const ps of result.program_statuses) {
      for (const gs of ps.group_statuses) traverse(gs, ps.program_id)
    }
    return map
  }, [result])

  // Reverse prereq map: courseId → [courseIds that require it as a prereq].
  // Lets us show "Unlocks: ISYE 313, ISYE 315" on the STAT 309 card.
  const prereqEnables = useMemo(() => {
    const map = {}
    const allCourses = [...result.recommended_courses, ...(result.prereq_only_courses || [])]
    for (const c of allCourses) {
      for (const prereqId of (c.missing_prereqs || [])) {
        // Expand to the full OR group so all alternatives show "Unlocks…"
        const orGroup = _getPrereqOrGroup(c.course_id, prereqId, courseMap)
        for (const altId of orGroup) {
          if (!map[altId]) map[altId] = []
          if (!map[altId].includes(c.course_id)) map[altId].push(c.course_id)
        }
      }
    }
    return map
  }, [result, courseMap])

  // Build DARS-style sections: one entry per top-level group_status per program.
  const programSections = useMemo(
    () => buildDARSSections(result, courseMap, hasIEandDS, oneOfChoices),
    [result, courseMap, hasIEandDS, oneOfChoices]
  )

  // Flat list of all leaf rows from unsatisfied sections (drives selections state).
  const allRows = useMemo(
    () => programSections.flatMap(p => p.sections.flatMap(s => s.rows)),
    [programSections]
  )

  // selections: { groupId → Set<courseId> }
  const [selections, setSelections] = useState(() => initSelections(allRows))

  // Notify parent whenever selections change so SummaryBanner and ProgramStatus can update.
  //
  // We do three things here that the naive version missed:
  //
  // 1. ALL_REQUIRED rows: courses like INTEREGR_397 are forced into the plan even though the
  //    user never clicks them.  Including them here means comm_engineering (and any other
  //    all_required group) shows ✓ in the program checklist.
  //
  // 2. Alternative-choice courses: a course may live only in `alternativeIds` (it isn't in
  //    recommended_courses), so courseMap has it with satisfies_groups: [].  We enrich each
  //    course's satisfies_groups with the group IDs of every row it appears in so that the
  //    plannedGroupIds set (built in ProgramStatus) gets the right group_ids.
  //
  // 3. Planned-credits accounting: the SummaryBanner uses satisfies_groups to credit planned
  //    credits toward each program's progress bar, so point 2 also fixes the bar.
  useEffect(() => {
    if (!onSelectionsChange) return

    const selectedIds = new Set()
    for (const ids of Object.values(selections)) ids.forEach(id => selectedIds.add(id))

    // (1) Always include ALL_REQUIRED mandatory courses.
    for (const row of allRows) {
      if (row.type === 'all_required') {
        ;(row.group.missing_required || []).forEach(id => selectedIds.add(id))
      }
    }

    // (2) Build a map: courseId → [groupIds] based on which rows each course appears in.
    //     This is used to enrich courses whose satisfies_groups is empty (alternative choices).
    const courseToGroupIds = {}
    for (const row of allRows) {
      const ids = [
        ...row.recommendedIds,
        ...row.alternativeIds,
        ...(row.type === 'all_required' ? (row.group.missing_required || []) : []),
      ]
      for (const id of ids) {
        if (!courseToGroupIds[id]) courseToGroupIds[id] = []
        if (!courseToGroupIds[id].includes(row.group.group_id)) {
          courseToGroupIds[id].push(row.group.group_id)
        }
      }
    }

    const planned = [...selectedIds].map(id => {
      const course = courseMap[id]
      if (!course) return null

      // Merge optimizer-supplied satisfies_groups with row-derived group IDs so that
      // alternative-choice selections (satisfies_groups: []) still light up the right circles.
      const rowGroups   = courseToGroupIds[id] || []
      const existingGroups = course.satisfies_groups || []
      if (rowGroups.length === 0) return course
      const mergedGroups = [...new Set([...existingGroups, ...rowGroups])]
      return mergedGroups.length === existingGroups.length
        ? course
        : { ...course, satisfies_groups: mergedGroups }
    }).filter(Boolean)

    onSelectionsChange(planned)
  // allRows is memoized from programSections which is memoized — safe dep.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selections, courseMap, onSelectionsChange, allRows])

  // When a DARS import arrives, pre-fill selections for every group that has a
  // matching course in the imported plan.  This mirrors what the user would do
  // manually — click each course they've already scheduled.
  useEffect(() => {
    if (!importedCourseIds || importedCourseIds.length === 0) return
    const darsSet = new Set(importedCourseIds)

    setSelections(prev => {
      const next = { ...prev }
      for (const row of allRows) {
        if (row.type === 'all_required') continue   // auto-filled, not user-selectable
        const allIds = [...row.recommendedIds, ...row.alternativeIds]
        const matches = allIds.filter(id => darsSet.has(id))
        if (matches.length === 0) continue

        const currentSel = new Set(prev[row.group.group_id] || [])
        // Never overwrite selections the user already made manually.
        if (currentSel.size > 0) continue
        if (row.type === 'one_of') {
          // ONE_OF: pick the first DARS match (radio-style)
          next[row.group.group_id] = new Set([matches[0]])
        } else {
          // CHOOSE_N / open-ended: add all matches
          matches.forEach(id => currentSel.add(id))
          next[row.group.group_id] = currentSel
        }
      }
      return next
    })
  // importedCourseIds identity changes when a new import arrives; allRows changes
  // when the result changes.  We intentionally omit `setSelections` (stable ref).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importedCourseIds, allRows])

  function toggleSelection(groupId, courseId, mode) {
    // Find which top-level section this group belongs to.
    // Cross-linking is skipped for sibling rows in the SAME section — within a
    // section, the excludeIds filter handles visibility so a course selected for
    // "IDA Core" disappears from "Additional Electives" without being mirrored
    // into Additional's selection Set (which would cause it to vanish from IDA
    // Core too when excludeIds is computed).
    const currentRow = allRows.find(r => r.group.group_id === groupId)
    const currentSectionId = currentRow?.sectionId

    setSelections(prev => {
      const isAdding = mode === 'radio' ? true : !(prev[groupId]?.has(courseId))
      const next = { ...prev }

      if (mode === 'radio') {
        next[groupId] = new Set([courseId])
      } else {
        const updated = new Set(prev[groupId] || [])
        if (updated.has(courseId)) updated.delete(courseId)
        else updated.add(courseId)
        next[groupId] = updated
      }

      // Cross-link: mirror selection into every other choice group listing this
      // course — but SKIP rows that belong to the same top-level section UNLESS
      // that section is a shared-pool section (e.g. liberal_studies), where the
      // same course intentionally satisfies multiple sub-requirements at once.
      const currentRowIsSharedPool = currentRow?.isSharedPool ?? false
      for (const row of allRows) {
        if (row.type === 'all_required') continue
        if (row.group.group_id === groupId) continue
        // Same section → skip UNLESS both rows are in a shared pool section.
        if (currentSectionId && row.sectionId === currentSectionId && !currentRowIsSharedPool) continue
        // Distinct-from exclusion: if the target row excludes courses selected in
        // the source group (e.g. math_307_699 distinctFrom math_400_699), don't
        // mirror the selection — it would cause credit double-counting even though
        // the excludeIds mechanism hides the course from display.
        if ((row.distinctFromGroups || []).includes(groupId)) continue
        const allIds = [...row.recommendedIds, ...row.alternativeIds]
        if (!allIds.includes(courseId)) continue
        const groupSel = new Set(prev[row.group.group_id] || [])
        if (isAdding) groupSel.add(courseId)
        else groupSel.delete(courseId)
        next[row.group.group_id] = groupSel
      }

      return next
    })
  }

  // Warning state: null when hidden, { extras: string[], allCourses: CourseRec[] } when shown.
  const [extraWarning, setExtraWarning] = useState(null)

  /** Build the full course list that would be passed to onConfirm. */
  function buildCourseList(selectedIds) {
    // Primary: courses from the optimizer's recommendation list that the user selected.
    const finalCourses = result.recommended_courses.filter(c => selectedIds.has(c.course_id))
    const finalCourseIds = new Set(finalCourses.map(c => c.course_id))

    // Prereq-only courses needed by the selected courses.
    const prereqsNeeded = result.prereq_only_courses.filter(c =>
      result.recommended_courses.some(rc =>
        selectedIds.has(rc.course_id) && rc.missing_prereqs.includes(c.course_id)
      )
    )
    const allPlannedIds = new Set([
      ...finalCourseIds,
      ...prereqsNeeded.map(c => c.course_id),
    ])

    // Secondary: courses the user selected from alternativeIds that are NOT in
    // the optimizer's recommendation list (e.g. user chose ECON 301 but the
    // optimizer auto-picked a French course for the depth condition).
    const altCourses = []
    for (const id of selectedIds) {
      if (allPlannedIds.has(id)) continue
      const c = courseMap[id]
      if (!c) continue
      const missingPrereqs = (c.prerequisites || []).flatMap(orGroup => {
        const plannedOption = orGroup.find(p => allPlannedIds.has(p))
        return plannedOption ? [plannedOption] : []
      })
      altCourses.push({
        course_id: c.course_id,
        name: c.name,
        credits: c.credits,
        offered: c.offered || [],
        satisfies_groups: c.satisfies_groups || [],
        overlap_score: c.overlap_score || 0,
        can_take_now: missingPrereqs.length === 0,
        missing_prereqs: missingPrereqs,
        co_requisites: c.co_requisites || [],
        concurrent_prereqs: c.concurrent_prereqs || [],
        is_prereq_filler: false,
      })
    }

    return [...finalCourses, ...altCourses, ...prereqsNeeded]
  }

  function handleConfirm() {
    // Collect all selected IDs (user picks + mandatory all_required courses).
    const selectedIds = new Set()
    for (const ids of Object.values(selections)) ids.forEach(id => selectedIds.add(id))
    for (const row of allRows) {
      if (row.type === 'all_required') row.group.missing_required.forEach(id => selectedIds.add(id))
    }

    const allCourses = buildCourseList(selectedIds)

    // Detect extra courses — ones that exceed what any requirement actually needs.
    const extras = findExtraCourses(selections, allRows, courseMap)

    if (extras.length > 0) {
      setExtraWarning({ extras, allCourses })
    } else {
      onConfirm(allCourses)
    }
  }

  const totalSelected = useMemo(() => {
    const ids = new Set()
    allRows.forEach(row => {
      if (row.type === 'all_required') {
        row.group.missing_required.forEach(id => ids.add(id))
      } else {
        const sel = selections[row.group.group_id]
        if (sel) sel.forEach(id => ids.add(id))
      }
    })
    return ids.size
  }, [selections, allRows])

  // Only list prereq-only courses that are actually needed by currently-selected courses.
  // This avoids showing "Also needed as prerequisites: GEOG 573 · MATH 531" when none of
  // the courses that require those prereqs have been selected yet.
  const relevantPrereqs = useMemo(() => {
    const selectedIds = new Set()
    for (const ids of Object.values(selections)) ids.forEach(id => selectedIds.add(id))
    // All-required rows are always included (they're mandatory, not user-toggled).
    for (const row of allRows) {
      if (row.type === 'all_required') {
        row.group.missing_required.forEach(id => selectedIds.add(id))
      }
    }
    return result.prereq_only_courses.filter(prereq =>
      result.recommended_courses.some(rc =>
        selectedIds.has(rc.course_id) && rc.missing_prereqs.includes(prereq.course_id)
      )
    )
  }, [selections, allRows, result])

  const hasAnySections = programSections.some(p => p.sections.length > 0)
  const hasAnyUnsatisfied = allRows.length > 0

  if (!hasAnySections) {
    return (
      <div className="req-empty">
        <p>All requirements are satisfied! 🎉</p>
      </div>
    )
  }

  return (
    <div className="req-panel">
      <div className="req-panel__header">
        <h3 className="req-panel__title">Requirements Checklist</h3>
        <p className="req-panel__desc">
          <strong style={{ color: 'var(--green)' }}>✓ Green</strong> — requirement complete. Click to expand and see which courses satisfied it.{' '}
          <strong style={{ color: 'var(--amber)' }}>⚠ Amber</strong> — still needed. The optimizer's recommended course is shown; click an alternative to swap.
        </p>
      </div>

      {programSections.map(({ programName, sections }) => {
        const allDone    = sections.every(s => s.satisfied)
        const allPlanned = !allDone && sections.every(s => {
          if (s.satisfied) return true
          return s.rows.every(row => {
            if (row.type === 'all_required') return true   // mandatory, always in plan
            const sel = selections[row.group.group_id] || new Set()
            if (row.type === 'n_credits') {
              const selCr = [...sel].reduce((sum, id) => sum + (courseMap[id]?.credits || 0), 0)
              return selCr >= (row.group.credits_still_needed || 0)
            }
            return sel.size >= (row.group.courses_still_needed || 1)
          })
        })

        return (
          <div key={programName} className="req-program-section">
            <h4 className="req-program-name">
              {programName}
              {allDone && (
                <span className="req-program-badge req-program-badge--done" title="All requirements complete">
                  ✓ Complete
                </span>
              )}
              {allPlanned && (
                <span className="req-program-badge req-program-badge--planned" title="All requirements selected — ready to plan">
                  ✓ On Track
                </span>
              )}
            </h4>
            <div className="dars-sections">
              {sections.map(section => (
                <DARSSection
                  key={section.topGroupId}
                  section={section}
                  selections={selections}
                  onToggle={toggleSelection}
                  courseMap={courseMap}
                  groupToProgram={groupToProgram}
                  prereqEnables={prereqEnables}
                  onPickOneOf={onPickOneOf}
                  allRows={allRows}
                />
              ))}
            </div>
          </div>
        )
      })}

      {/* Prereq-only courses note — only shown when the relevant course is selected */}
      {relevantPrereqs.length > 0 && (
        <div className="req-prereqs-note">
          <span className="req-prereqs-note__label">Also needed as prerequisites:</span>
          <span className="req-prereqs-note__list">
            {relevantPrereqs.map(c => c.course_id.replace(/_/g, ' ')).join(' · ')}
          </span>
        </div>
      )}

      {/* Open-ended requirements */}
      {result.unresolved_groups.length > 0 && (
        <div className="alert alert--warning req-unresolved">
          <strong>Open-ended requirements need advisor input:</strong>{' '}
          {result.unresolved_groups.map(g => g.group_name).join(', ')}
        </div>
      )}

      {/* Extra-course warning — shown when handleConfirm detects redundant selections */}
      {extraWarning && (
        <div className="req-extra-warning">
          <p className="req-extra-warning__title">
            ⚠ {extraWarning.extras.length === 1 ? 'This course is' : 'These courses are'} not needed
          </p>
          <p className="req-extra-warning__body">
            {extraWarning.extras.length === 1
              ? "This course doesn’t fill any remaining requirement — your other selections already cover it."
              : "These courses don’t fill any remaining requirements — your other selections already cover them."}
          </p>
          <ul className="req-extra-warning__list">
            {extraWarning.extras.map(id => {
              const c = courseMap[id]
              const display = id.replace(/_/g, ' ')
              return (
                <li key={id}>
                  <strong>{display}</strong>
                  {c?.name && c.name !== display && ` — ${c.name}`}
                </li>
              )
            })}
          </ul>
          <div className="req-extra-warning__actions">
            <button
              className="btn btn--primary"
              onClick={() => {
                const extraSet = new Set(extraWarning.extras)
                onConfirm(extraWarning.allCourses.filter(c => !extraSet.has(c.course_id)))
                setExtraWarning(null)
              }}
            >
              Remove &amp; Build Plan
            </button>
            <button
              className="btn btn--ghost"
              onClick={() => { onConfirm(extraWarning.allCourses); setExtraWarning(null) }}
            >
              Keep them &amp; Build Anyway
            </button>
            <button
              className="btn btn--ghost"
              onClick={() => setExtraWarning(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {hasAnyUnsatisfied && (
        <div className="req-panel__footer">
          <span className="req-panel__count">{totalSelected} courses selected</span>
          <button className="btn btn--primary btn--lg" onClick={handleConfirm}>
            Build My Semester Plan →
          </button>
        </div>
      )}
    </div>
  )
}


/* --------------------------------------------------------------------------
   DARSSection — one top-level requirement category
   -------------------------------------------------------------------------- */

function DARSSection({ section, selections, onToggle, courseMap, groupToProgram, prereqEnables, onPickOneOf, allRows = [] }) {
  // Satisfied sections start collapsed; unsatisfied start expanded.
  const [expanded, setExpanded] = useState(!section.satisfied)
  const { topGroupName, satisfied, completedCourses, rows, statusLabel, focusPicker, isSharedPool } = section

  return (
    <div className={`dars-section ${satisfied ? 'dars-section--satisfied' : 'dars-section--unsatisfied'}`}>
      <button
        className="dars-section__header"
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
      >
        <span className={`dars-section__icon ${satisfied ? 'dars-section__icon--done' : 'dars-section__icon--warn'}`}>
          {satisfied ? '✓' : '⚠'}
        </span>
        <span className="dars-section__name">{topGroupName}</span>
        {statusLabel && (
          <span className={`dars-section__status ${satisfied ? 'dars-section__status--done' : 'dars-section__status--warn'}`}>
            {statusLabel}
          </span>
        )}
        <span className="dars-section__chevron">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="dars-section__content">
          {satisfied ? (
            /* ── Completed courses list ─────────────────────── */
            <div className="dars-completed-list">
              {completedCourses.length === 0 ? (
                <p className="dars-section__empty-note">
                  Satisfied via credit transfer, AP credit, or placement.
                </p>
              ) : (
                completedCourses.map(id => {
                  const c = courseMap[id]
                  const displayId = id.replace(/_/g, ' ')
                  return (
                    <div key={id} className="dars-completed-course">
                      <span className="dars-completed-course__id">{displayId}</span>
                      {c && c.name && c.name !== displayId && (
                        <span className="dars-completed-course__name">{c.name}</span>
                      )}
                      {c && c.credits && (
                        <span className="dars-completed-course__credits">{c.credits} cr</span>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          ) : (
            /* ── Unsatisfied: focus picker + leaf requirement rows ─── */
            <div className="req-group-list dars-section__rows">
              {/* Focus area (or any one_of) picker */}
              {focusPicker && (
                <div className="focus-picker">
                  <p className="focus-picker__label">Select your focus area:</p>
                  <div className="focus-picker__options">
                    {focusPicker.options.map(opt => (
                      <button
                        key={opt.id}
                        className={[
                          'focus-picker__btn',
                          focusPicker.currentChoiceId === opt.id ? 'focus-picker__btn--active' : '',
                          opt.satisfied ? 'focus-picker__btn--done' : '',
                        ].join(' ')}
                        onClick={() => onPickOneOf && onPickOneOf(focusPicker.parentGroupId, opt.id)}
                      >
                        {opt.satisfied ? '✓ ' : ''}{opt.name}
                      </button>
                    ))}
                  </div>
                  {focusPicker.currentChoiceId && (
                    <p className="focus-picker__hint">
                      Showing requirements for <strong>{focusPicker.options.find(o => o.id === focusPicker.currentChoiceId)?.name}</strong>.
                      Recommendations update when you switch.
                    </p>
                  )}
                </div>
              )}

              {rows.length === 0 ? (
                <p className="dars-section__empty-note">
                  No specific courses listed — consult your advisor for eligible options.
                </p>
              ) : (
                rows.map(row => {
                  // Build excludedWithSource: Map<courseId, sourceGroupName> for
                  // courses in this row's pool that are already selected elsewhere.
                  // These are rendered as non-interactive "Counted for: X" notes
                  // rather than being silently removed.
                  const thisOptions = new Set([...row.recommendedIds, ...row.alternativeIds])
                  const excludedWithSource = new Map()

                  // Within-section exclusion: skip when sub-groups share a course
                  // pool (e.g. liberal_studies) — the same course intentionally
                  // satisfies multiple sub-requirements simultaneously.
                  // For IDA focus area, core/outside courses are correctly excluded
                  // from Additional ISyE Electives so each pool stays distinct.
                  if (!isSharedPool) {
                    for (const otherRow of rows) {
                      if (otherRow.group.group_id === row.group.group_id) continue
                      const otherSelected = selections[otherRow.group.group_id] || new Set()
                      for (const id of otherSelected) {
                        if (thisOptions.has(id)) {
                          excludedWithSource.set(id, otherRow.group.group_name)
                        }
                      }
                    }
                  }

                  // Cross-section exclusion: courses selected in groups listed in
                  // this row's distinct_from_groups must not appear here
                  // (e.g. consulting_certificate additional_coursework must not
                  //  re-list courses already used for foundation or analytics).
                  for (const distinctGroupId of (row.distinctFromGroups || [])) {
                    const otherSelected = selections[distinctGroupId] || new Set()
                    // Look up the group name from all rows (cross-section lookup).
                    const sourceRow = allRows.find(r => r.group.group_id === distinctGroupId)
                    const sourceName = sourceRow?.group.group_name
                      ?? distinctGroupId.replace(/_/g, ' ')
                    for (const id of otherSelected) {
                      if (thisOptions.has(id)) {
                        excludedWithSource.set(id, sourceName)
                      }
                    }
                  }

                  return (
                    <RequirementGroupRow
                      key={row.group.group_id}
                      row={row}
                      selections={selections}
                      onToggle={onToggle}
                      courseMap={courseMap}
                      groupToProgram={groupToProgram}
                      prereqEnables={prereqEnables}
                      excludedWithSource={excludedWithSource}
                    />
                  )
                })
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}


/* --------------------------------------------------------------------------
   RequirementGroupRow — one leaf requirement inside an unsatisfied section
   -------------------------------------------------------------------------- */

function RequirementGroupRow({ row, selections, onToggle, courseMap, groupToProgram, prereqEnables, excludedWithSource = new Map() }) {
  const [showAll, setShowAll] = useState(false)
  const { group, recommendedIds, alternativeIds, type } = row
  const groupId = group.group_id
  const selected = selections[groupId] || new Set()

  const isAllRequired = type === 'all_required'
  const selectionMode =
    type === 'one_of' || (type === 'n_courses' && group.courses_still_needed === 1)
      ? 'radio'
      : 'checkbox'

  // ALL_REQUIRED: flat list of missing courses (locked, must-take)
  if (isAllRequired) {
    const courses = group.missing_required.map(id => courseMap[id]).filter(Boolean)
    return (
      <div className="req-group">
        <div className="req-group__header">
          <span className="req-group__name">{group.group_name}</span>
          <span className="req-group__tag req-group__tag--required">All required</span>
        </div>
        <div className="req-group__courses">
          {courses.map(c => (
            <CourseOption
              key={c.course_id}
              course={c}
              selected={true}
              locked={true}
              groupToProgram={groupToProgram}
              prereqEnables={prereqEnables}
              courseMap={courseMap}
            />
          ))}
          {group.missing_required
            .filter(id => !courseMap[id])
            .map(id => (
              <CourseOption
                key={id}
                course={{ course_id: id, name: '', credits: null }}
                selected={true}
                locked={true}
                groupToProgram={groupToProgram}
                prereqEnables={prereqEnables}
                courseMap={courseMap}
              />
            ))}
        </div>
      </div>
    )
  }

  // Choice groups (one_of / n_courses / n_credits).
  // Separate selectable options from excluded courses (already counted elsewhere).
  const allOptions = [...recommendedIds, ...alternativeIds].filter(id => !excludedWithSource.has(id))
  const visibleOptions = showAll ? allOptions : allOptions.slice(0, 3)
  const hiddenCount = allOptions.length - 3

  // Courses excluded because they're already selected for a sibling requirement.
  // Shown as non-interactive "Counted for: X" ghost entries so the student
  // knows where those courses are going.
  const excludedEntries = [...recommendedIds, ...alternativeIds]
    .filter(id => excludedWithSource.has(id))
    // Deduplicate (course may be in both recommended and alternative lists).
    .filter((id, i, arr) => arr.indexOf(id) === i)
    .map(id => ({ id, source: excludedWithSource.get(id) }))

  // Credit/course tracker: count how many credits (or courses) the student
  // has selected toward this group's budget so far.
  const selectedCredits = type === 'n_credits'
    ? [...selected].reduce((sum, id) => sum + (courseMap[id]?.credits || 0), 0)
    : 0
  const selectedCount = selected.size

  let needLabel = null
  let needLabelProgress = false   // true → show green "X / Y" progress style
  if (type === 'n_credits' && group.credits_still_needed > 0) {
    if (selectedCredits > 0) {
      needLabel = `${selectedCredits} / ${group.credits_still_needed} cr selected`
      needLabelProgress = true
    } else {
      needLabel = `${group.credits_still_needed} cr needed`
    }
  } else if (group.courses_still_needed > 0) {
    const total = group.courses_still_needed
    needLabel = `${selectedCount} / ${total} course${total !== 1 ? 's' : ''} selected`
    needLabelProgress = selectedCount > 0
  }

  const typeLabel =
    type === 'one_of'    ? 'Choose 1' :
    type === 'n_courses' ? `Choose ${group.courses_still_needed}` :
    type === 'n_credits' ? `Choose ${group.credits_still_needed} cr` :
    ''

  return (
    <div className="req-group">
      <div className="req-group__header">
        <span className="req-group__name">{group.group_name}</span>
        <div className="req-group__header-right">
          {needLabel && (
            <span className={`req-group__need ${needLabelProgress ? 'req-group__need--progress' : ''}`}>
              {needLabel}
            </span>
          )}
          {typeLabel && <span className="req-group__tag">{typeLabel}</span>}
        </div>
      </div>

      <div className="req-group__courses">
        {allOptions.length === 0 && (
          <div className="req-group__open-ended">
            {/* List specific courses already counted toward this open-ended group */}
            {group.completed_courses && group.completed_courses.length > 0 && (
              <div className="req-group__completed-list">
                <p className="req-group__completed-label">Courses already counted here:</p>
                {group.completed_courses.map(id => {
                  const c = courseMap[id]
                  const displayId = id.replace(/_/g, ' ')
                  return (
                    <div key={id} className="dars-completed-course">
                      <span className="dars-completed-course__id">{displayId}</span>
                      {c?.name && c.name !== displayId && (
                        <span className="dars-completed-course__name">{c.name}</span>
                      )}
                      {c?.credits && (
                        <span className="dars-completed-course__credits">{c.credits} cr</span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            {/* Fallback: if there are completed credits but no specific course list */}
            {group.credits_completed > 0 && (!group.completed_courses || group.completed_courses.length === 0) && (
              <p className="req-group__open-ended-applied">
                ✓ {group.credits_completed} cr of AP/transfer credit already counted here.
              </p>
            )}
            {group.credits_still_needed > 0 && (
              <p className="req-group__empty">
                {group.credits_still_needed} cr still needed — any eligible course counts. Add it to your manual course list.
              </p>
            )}
            {group.credits_still_needed === 0 && group.courses_still_needed === 0 && (!group.completed_courses || group.completed_courses.length === 0) && (
              <p className="req-group__empty">Fully satisfied by AP/transfer credit.</p>
            )}
            {group.courses_still_needed > 0 && (
              <p className="req-group__empty">
                {group.courses_still_needed} more course{group.courses_still_needed > 1 ? 's' : ''} needed — add an eligible course to your completed list above.
              </p>
            )}
          </div>
        )}
        {visibleOptions.map(id => {
          const course = courseMap[id]
          const isSelected = selected.has(id)
          const isRecommended = recommendedIds.includes(id)
          if (course) {
            return (
              <CourseOption
                key={id}
                course={course}
                selected={isSelected}
                recommended={isRecommended}
                onToggle={() => onToggle(groupId, id, selectionMode)}
                groupToProgram={groupToProgram}
                prereqEnables={prereqEnables}
                courseMap={courseMap}
              />
            )
          }
          return (
            <AltOption
              key={id}
              courseId={id}
              selected={isSelected}
              onToggle={() => onToggle(groupId, id, selectionMode)}
            />
          )
        })}

        {!showAll && hiddenCount > 0 && (
          <button className="req-group__show-more" onClick={() => setShowAll(true)}>
            ··· {hiddenCount} more option{hiddenCount > 1 ? 's' : ''}
          </button>
        )}
        {showAll && hiddenCount > 0 && (
          <button className="req-group__show-more" onClick={() => setShowAll(false)}>
            Show fewer
          </button>
        )}

        {/* "Counted for" ghost entries — courses already selected in a sibling
            requirement are shown here as non-interactive notes so the student
            knows where each course is being applied. */}
        {excludedEntries.length > 0 && (
          <div className="req-group__excluded">
            {excludedEntries.map(({ id, source }) => (
              <ExcludedCourseNote
                key={id}
                courseId={id}
                source={source}
                courseMap={courseMap}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}


/* --------------------------------------------------------------------------
   ExcludedCourseNote — non-interactive ghost entry for courses counted elsewhere
   -------------------------------------------------------------------------- */

/**
 * Shown when a course appears in this group's pool but has already been
 * selected for a sibling requirement (e.g. ISYE 373 selected for IDA Core
 * appears here in Additional ISyE Electives as a grayed-out note).
 */
function ExcludedCourseNote({ courseId, source, courseMap }) {
  const course = courseMap[courseId]
  const displayId = courseId.replace(/_/g, ' ')
  return (
    <div className="course-option course-option--excluded" aria-label={`${displayId} counted for ${source}`}>
      <span className="course-option__check course-option__check--excluded">↳</span>
      <span className="course-option__id">{displayId}</span>
      {course?.name && course.name !== displayId && (
        <span className="course-option__name">{course.name}</span>
      )}
      <div className="course-option__badges">
        {course?.credits && (
          <span className="badge badge--credits">{course.credits} cr</span>
        )}
        <span className="badge badge--counted-for">Counted for: {source}</span>
      </div>
    </div>
  )
}


/* --------------------------------------------------------------------------
   CourseOption / AltOption — selectable course chips
   -------------------------------------------------------------------------- */

function CourseOption({ course, selected, recommended, locked, onToggle, groupToProgram = {}, prereqEnables = {}, courseMap = {} }) {
  // Compute how many distinct programs this course overlaps using satisfies_groups.
  // This is the real program count, not the backend's overlap_score (which counts groups).
  const overlapProgramCount = useMemo(() => {
    const programs = new Set()
    for (const gid of (course.satisfies_groups || [])) {
      const pid = groupToProgram[gid]
      if (pid) programs.add(pid)
    }
    return programs.size
  }, [course, groupToProgram])

  const isOverlap = overlapProgramCount > 1
  const overlapLabel = overlapProgramCount === 2 ? 'Both programs' : `${overlapProgramCount} programs`

  // Courses this one unlocks (i.e., it is a prereq for these courses).
  const unlocksIds = prereqEnables[course.course_id] || []
  // Missing prereqs (courses that must be taken before this one).
  const missingPrereqs = course.missing_prereqs || []
  const isBlocked = course.can_take_now === false && missingPrereqs.length > 0
  // Co-requisites: courses that must be taken in the same semester.
  const coReqs = course.co_requisites || []
  // Concurrent prereqs: prereqs that may be taken simultaneously with this course.
  const concurrentPrereqs = course.concurrent_prereqs || []

  return (
    <div
      className={[
        'course-option',
        selected  ? 'course-option--selected'  : '',
        locked    ? 'course-option--locked'    : '',
        isOverlap ? 'course-option--overlap'   : '',
      ].join(' ')}
      onClick={!locked ? onToggle : undefined}
      role={locked ? undefined : 'button'}
      tabIndex={locked ? undefined : 0}
      onKeyDown={e => { if (!locked && (e.key === 'Enter' || e.key === ' ')) onToggle() }}
    >
      <span className="course-option__check">{selected ? '✓' : '○'}</span>
      <span className="course-option__id">{course.course_id.replace(/_/g, ' ')}</span>
      {course.name && <span className="course-option__name">{course.name}</span>}
      <div className="course-option__badges">
        {course.credits && <span className="badge badge--credits">{course.credits} cr</span>}
        {isOverlap && <span className="badge badge--overlap">✦ {overlapLabel}</span>}
        {recommended && !locked && <span className="badge badge--recommended">Recommended</span>}
        {isBlocked && <span className="badge badge--blocked">Needs prereqs</span>}
        {coReqs.length > 0 && <span className="badge badge--coreq">Co-req</span>}
      </div>
      {isBlocked && (
        <p className="course-option__prereq-info course-option__prereq-info--needs">
          ⚠ Take first: {missingPrereqs.map(missingId => {
            const orGroup = _getPrereqOrGroup(course.course_id, missingId, courseMap)
            return orGroup.length > 1
              ? orGroup.map(id => id.replace(/_/g, ' ')).join(' or ')
              : missingId.replace(/_/g, ' ')
          }).join(', ')}
        </p>
      )}
      {coReqs.length > 0 && (
        <p className="course-option__prereq-info course-option__prereq-info--coreq">
          🔗 Must take same semester: {coReqs.map(id => id.replace(/_/g, ' ')).join(', ')}
        </p>
      )}
      {concurrentPrereqs.length > 0 && (
        <p className="course-option__prereq-info course-option__prereq-info--concurrent">
          ↔ Concurrent enrollment allowed with: {concurrentPrereqs.map(id => id.replace(/_/g, ' ')).join(', ')}
        </p>
      )}
      {unlocksIds.length > 0 && (
        <p className="course-option__prereq-info course-option__prereq-info--unlocks">
          🔓 Unlocks: {unlocksIds.map(id => id.replace(/_/g, ' ')).join(', ')}
        </p>
      )}
    </div>
  )
}

function AltOption({ courseId, selected, onToggle }) {
  return (
    <div
      className={`course-option course-option--alt ${selected ? 'course-option--selected' : ''}`}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
    >
      <span className="course-option__check">{selected ? '✓' : '○'}</span>
      <span className="course-option__id">{courseId.replace(/_/g, ' ')}</span>
    </div>
  )
}


/* --------------------------------------------------------------------------
   Helpers
   -------------------------------------------------------------------------- */

/**
 * Given a course and one of its missing prereqs, return the full OR group that
 * contains the missing prereq.  Uses catalog prerequisites stored in courseMap.
 *
 * Example: course ISYE_312 has prerequisites [['STAT_311', 'STAT_MATH_309']].
 * _getPrereqOrGroup('ISYE_312', 'STAT_311', courseMap)
 *   → ['STAT_311', 'STAT_MATH_309']
 *
 * Falls back to [missingId] if no OR group is found (single-prereq courses).
 */
function _getPrereqOrGroup(courseId, missingId, courseMap) {
  const course = courseMap[courseId]
  if (!course?.prerequisites) return [missingId]
  for (const orGroup of course.prerequisites) {
    if (orGroup.includes(missingId)) return orGroup
  }
  return [missingId]
}

/**
 * Detect "extra" courses — those selected by the student that exceed what any
 * requirement group actually needs.
 *
 * Algorithm:
 *  1. For each requirement row, determine which selected courses are excess
 *     (count > courses_still_needed, or credits > credits_still_needed).
 *  2. A course is TRULY extra only when it is excess in EVERY group whose
 *     selection contains it — i.e. no group actually needs it.
 *     (Cross-linking can add the same course to multiple groups; if it fills
 *     one group but overflows another, it is still needed.)
 *
 * Returns an array of course_ids that are safe to drop.
 */
function findExtraCourses(selections, allRows, courseMap) {
  // Courses that are mandatory (locked in any all_required row) can NEVER be
  // extra, even if they also appear pre-populated in a choice row via
  // initSelections (e.g. consulting cert GEN_BUS_370 pre-filled into IE BS
  // professional electives).
  const mandatoryIds = new Set()
  for (const row of allRows) {
    if (row.type === 'all_required') {
      for (const id of (row.group.missing_required || [])) mandatoryIds.add(id)
    }
  }

  // Step 1 — per-group excess sets.
  const excessByGroup = {}  // groupId → Set<courseId>

  for (const row of allRows) {
    if (row.type === 'all_required') continue          // mandatory, never extra
    const groupId = row.group.group_id
    const sel = [...(selections[groupId] || new Set())]
    if (sel.length === 0) continue

    if (row.type === 'one_of') {
      // Radio-style: at most 1 is ever meaningful.
      if (sel.length > 1) excessByGroup[groupId] = new Set(sel.slice(1))
    } else if (row.type === 'n_courses') {
      const need = row.group.courses_still_needed || 0
      if (need > 0 && sel.length > need) {
        excessByGroup[groupId] = new Set(sel.slice(need))
      }
    } else if (row.type === 'n_credits') {
      const need = row.group.credits_still_needed || 0
      if (need > 0) {
        let accum = 0
        const excess = new Set()
        for (const id of sel) {
          if (accum >= need) excess.add(id)
          accum += (courseMap[id]?.credits || 3)
        }
        if (excess.size > 0) excessByGroup[groupId] = excess
      }
    }
  }

  // Step 2 — only keep courses that are excess in ALL groups containing them.
  const allExcessCandidates = new Set()
  for (const s of Object.values(excessByGroup)) {
    for (const id of s) allExcessCandidates.add(id)
  }

  const extras = []
  for (const id of allExcessCandidates) {
    // Mandatory courses are always needed — never mark them as extra.
    if (mandatoryIds.has(id)) continue

    let neededSomewhere = false
    for (const row of allRows) {
      if (row.type === 'all_required') continue
      const groupId = row.group.group_id
      const sel = selections[groupId] || new Set()
      if (!sel.has(id)) continue
      // Course appears in this group's selection; is it excess here?
      if (!excessByGroup[groupId]?.has(id)) {
        neededSomewhere = true
        break
      }
    }
    if (!neededSomewhere) extras.push(id)
  }

  return extras
}

/** Recursively collect every completed course ID from a GroupStatus tree. */
function getAllCompleted(gs) {
  const set = new Set(gs.completed_courses || [])
  for (const ss of gs.sub_statuses || []) {
    for (const id of getAllCompleted(ss)) set.add(id)
  }
  return [...set]
}

/** Rough credit cost of a group status — used to pick the "best" ONE_OF child. */
function roughCost(gs) {
  if (gs.satisfied) return 0
  if (gs.sub_statuses && gs.sub_statuses.length > 0) {
    return gs.sub_statuses.reduce((s, ss) => s + roughCost(ss), 0) +
           (gs.missing_required?.length ?? 0) * 3
  }
  return (gs.credits_still_needed ?? 0) +
         (gs.courses_still_needed ?? 0) * 3 +
         (gs.missing_required?.length ?? 0) * 3
}

/**
 * True when a group is ONE_OF type with multiple child options.
 * Detected by: courses_still_needed===1, no credit tracking, no direct missing courses,
 * and more than one child sub-status.
 */
function isOneOfWithOptions(g) {
  return (
    g.courses_still_needed === 1 &&
    g.credits_still_needed === 0 &&
    (!g.missing_required || g.missing_required.length === 0) &&
    g.sub_statuses && g.sub_statuses.length > 1
  )
}

/** Guess requirement type from group shape. */
function guessType(g) {
  if (g.missing_required && g.missing_required.length > 0 && (!g.eligible_remaining || g.eligible_remaining.length === 0)) return 'all_required'
  if (g.credits_still_needed > 0) return 'n_credits'
  if (g.courses_still_needed > 1) return 'n_courses'
  if (g.courses_still_needed === 1) return 'one_of'
  return 'all_required'
}

/**
 * Compute a short status label for an unsatisfied section header.
 * Returns null when the status isn't easily summarizable (nested groups).
 */
function getStatusLabel(gs) {
  if (isOneOfWithOptions(gs)) {
    return `choose 1 of ${gs.sub_statuses.length}`
  }
  if (gs.credits_still_needed > 0) {
    return `${gs.credits_still_needed} cr needed`
  }
  // Group has its own missing courses (possibly alongside sub-groups)
  if (gs.missing_required?.length > 0) {
    return `${gs.missing_required.length} course${gs.missing_required.length > 1 ? 's' : ''} missing`
  }
  if (gs.courses_still_needed > 0 && !gs.sub_statuses?.length) {
    return `${gs.courses_still_needed} more needed`
  }
  return null
}

/**
 * Flatten the sub-tree of ONE unsatisfied top-level GroupStatus into leaf rows.
 * ONE_OF groups: only recurse into the single best (cheapest) child, unless
 *   the student has chosen a specific one via oneOfChoices.
 * ALL_REQUIRED groups: recurse into all unsatisfied children.
 *
 * IMPORTANT: A non-leaf group (one that has sub_statuses) can ALSO have its own
 * direct missing_required courses at the parent level — e.g. foundational_ds has
 * STAT_240 / STAT_340 / COMP_SCI_320 directly required at the top level while
 * also containing intro-programming and ethics sub-groups.  Without special
 * handling, those parent-level courses would never appear in any row and would be
 * invisible in the UI.  We surface them as a synthetic all_required row so they
 * show up alongside the sub-group rows.
 *
 * isSharedPool: true when sub-groups share a course pool (e.g. liberal_studies).
 *   Propagated onto each row so toggleSelection can allow within-section cross-
 *   linking and DARSSection can skip the excludeIds mechanism.
 *
 * oneOfChoices: { [groupId]: chosenSubGroupId } — user's focus area selections.
 */
function flattenGroupIntoRows(gs, programName, result, oneOfChoices = {}, isSharedPool = false) {
  // All rows produced by this call belong to the same top-level section.
  // Used by toggleSelection to skip cross-linking within the same section,
  // so a course selected in one sub-group (e.g. IDA Core) doesn't pollute
  // another sub-group's selections (e.g. Additional ISyE Electives).
  const sectionId = gs.group_id
  const rows = []

  /**
   * If a non-leaf group has its OWN direct required courses (missing_required at
   * the group level, not in any sub-group), push a synthetic all_required row for
   * them so they are visible alongside the sub-group rows.
   */
  // rowSharedPool defaults to the section-level isSharedPool but can be overridden
  // per-group when siblings share a course pool (e.g. IDA core/outside/additional).
  function maybePushParentDirectRow(g, rowSharedPool = isSharedPool) {
    if (!g.missing_required || g.missing_required.length === 0) return
    const recommendedIds = result.recommended_courses
      .filter(c => c.satisfies_groups.includes(g.group_id))
      .map(c => c.course_id)
    rows.push({ group: g, programName, type: 'all_required', recommendedIds, alternativeIds: [], sectionId, isSharedPool: rowSharedPool, distinctFromGroups: [] })
  }

  /**
   * If a non-leaf N_CREDITS / N_COURSES group has its OWN eligible courses at the
   * parent level (i.e. an open pool alongside the sub-groups), push a choice row
   * for those parent-level courses so they are visible and selectable.
   *
   * Example: math_307_699 has three ONE_OF sub-groups (Linear Algebra, Differential
   * Equations, Probability) plus a large open pool of 400+ courses at the parent
   * level. Without this row the open pool would be invisible in the UI.
   */
  function maybePushParentChoiceRow(g, rowSharedPool = isSharedPool) {
    if (isOneOfWithOptions(g)) return  // ONE_OF parents use pickOneOfChild instead
    const eligible = g.eligible_remaining || []
    if (eligible.length === 0) return
    const recommendedIds = result.recommended_courses
      .filter(c => c.satisfies_groups.includes(g.group_id))
      .map(c => c.course_id)
    const alternativeIds = eligible.filter(id => !recommendedIds.includes(id))
    if (recommendedIds.length === 0 && alternativeIds.length === 0) return
    rows.push({
      group: g, programName, type: guessType(g),
      recommendedIds, alternativeIds, sectionId,
      isSharedPool: rowSharedPool,
      distinctFromGroups: g.distinct_from_groups || [],
    })
  }

  function pickOneOfChild(g) {
    const unsatisfied = g.sub_statuses.filter(s => !s.satisfied)
    if (unsatisfied.length === 0) return null
    const override = oneOfChoices[g.group_id]
    if (override) {
      return unsatisfied.find(s => s.group_id === override)
          ?? unsatisfied.reduce((a, b) => roughCost(a) <= roughCost(b) ? a : b)
    }
    return unsatisfied.reduce((a, b) => roughCost(a) <= roughCost(b) ? a : b)
  }

  function recurse(groups) {
    for (const g of groups) {
      if (g.satisfied) continue

      if (g.sub_statuses && g.sub_statuses.length > 0) {
        // Surface any parent-level direct requirements before diving into sub-groups.
        maybePushParentDirectRow(g)
        // Surface parent-level open-pool courses (e.g. math_307_699's 400+ pool
        // alongside its Linear Algebra / DE / Probability sub-groups).
        maybePushParentChoiceRow(g)

        if (isOneOfWithOptions(g)) {
          const chosen = pickOneOfChild(g)
          if (chosen) recurse([chosen])
        } else {
          recurse(g.sub_statuses)
        }
      } else {
        // Leaf group
        const recommendedIds = result.recommended_courses
          .filter(c => c.satisfies_groups.includes(g.group_id))
          .map(c => c.course_id)
        const alternativeIds = (g.eligible_remaining || [])
          .filter(id => !recommendedIds.includes(id))
        rows.push({
          group: g, programName, type: guessType(g),
          recommendedIds, alternativeIds, sectionId,
          isSharedPool,
          distinctFromGroups: g.distinct_from_groups || [],
        })
      }
    }
  }

  // Handle the top-level gs itself
  if (gs.sub_statuses && gs.sub_statuses.length > 0) {
    // Surface any parent-level direct requirements on the top-level group.
    maybePushParentDirectRow(gs)
    // Surface parent-level open-pool courses alongside sub-group rows.
    maybePushParentChoiceRow(gs)

    if (isOneOfWithOptions(gs)) {
      const chosen = pickOneOfChild(gs)
      if (chosen) recurse([chosen])
    } else {
      recurse(gs.sub_statuses)
    }
  } else {
    // Top-level is itself a leaf
    const recommendedIds = result.recommended_courses
      .filter(c => c.satisfies_groups.includes(gs.group_id))
      .map(c => c.course_id)
    const alternativeIds = (gs.eligible_remaining || [])
      .filter(id => !recommendedIds.includes(id))
    rows.push({
      group: gs, programName, type: guessType(gs),
      recommendedIds, alternativeIds, sectionId,
      isSharedPool,
      distinctFromGroups: gs.distinct_from_groups || [],
    })
  }

  return rows
}

/**
 * Build the DARS-style section structure.
 * Returns: [{programName, sections: [{topGroupId, topGroupName, satisfied, statusLabel,
 *            completedCourses, focusPicker, rows}]}]
 *
 * oneOfChoices: { [groupId]: chosenSubGroupId } — user's focus area selections.
 * When a top-level group is a ONE_OF picker (e.g. focus_area), a focusPicker
 * descriptor is added to the section so DARSSection can render the picker UI.
 */
function buildDARSSections(result, courseMap, hasIEandDS, oneOfChoices = {}) {
  return result.program_statuses.map(ps => {
    const sections = []

    for (const gs of ps.group_statuses) {
      // Skip L&S-only groups when the student is in the IE+DS double major.
      if (hasIEandDS && gs.group_id.startsWith(LS_WAIVED_PREFIX)) continue

      if (gs.satisfied) {
        sections.push({
          topGroupId: gs.group_id,
          topGroupName: gs.group_name,
          satisfied: true,
          statusLabel: `${getAllCompleted(gs).length} course${getAllCompleted(gs).length !== 1 ? 's' : ''}`,
          completedCourses: getAllCompleted(gs),
          focusPicker: null,
          rows: [],
        })
      } else {
        // For ONE_OF groups with multiple children (like focus_area), build
        // a picker descriptor so the section can render a focus area selector.
        let focusPicker = null
        if (isOneOfWithOptions(gs)) {
          focusPicker = {
            parentGroupId: gs.group_id,
            options: gs.sub_statuses.map(s => ({
              id: s.group_id,
              name: s.group_name,
              satisfied: s.satisfied,
            })),
            currentChoiceId: oneOfChoices[gs.group_id] || null,
          }
        }

        // Detect whether sub-groups share a course pool (e.g. liberal_studies).
        // When true, the excludeIds mechanism and the sectionId cross-link guard
        // are both relaxed so courses can satisfy multiple sub-requirements at once.
        const isSharedPool = !focusPicker && gs.sub_statuses.length > 0 && (() => {
          const seen = new Set()
          for (const ss of gs.sub_statuses) {
            const pool = [...(ss.missing_required || []), ...(ss.eligible_remaining || [])]
            for (const id of pool) {
              if (seen.has(id)) return true
              seen.add(id)
            }
          }
          return false
        })()

        sections.push({
          topGroupId: gs.group_id,
          topGroupName: gs.group_name,
          satisfied: false,
          statusLabel: getStatusLabel(gs),
          completedCourses: [],
          focusPicker,
          isSharedPool,
          rows: flattenGroupIntoRows(gs, ps.program_name, result, oneOfChoices, isSharedPool),
        })
      }
    }

    return { programName: ps.program_name, sections }
  })
}

/** Initialize selections — empty Sets for all choice leaf rows.
 *  Also pre-populates mandatory all_required courses into any choice row that
 *  lists the same course (e.g. REAL_EST_306 locked in real_estate_required
 *  should also appear pre-selected in bba_signature_one).
 */
function initSelections(rows) {
  // Collect every course that is mandatory (locked) across ALL_REQUIRED rows.
  const mandatoryIds = new Set()
  for (const row of rows) {
    if (row.type === 'all_required') {
      for (const id of (row.group.missing_required || [])) mandatoryIds.add(id)
    }
  }

  const sel = {}
  for (const row of rows) {
    if (row.type === 'all_required') continue
    const initial = new Set()
    // Pre-select mandatory courses that appear among this row's options.
    const pool = new Set([...row.recommendedIds, ...row.alternativeIds])
    for (const id of mandatoryIds) {
      if (pool.has(id)) initial.add(id)
    }
    sel[row.group.group_id] = initial
  }
  return sel
}
