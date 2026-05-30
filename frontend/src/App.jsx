import { useState, useEffect, useMemo, useCallback } from 'react'
import { fetchPrograms, fetchApExams, fetchCatalog, optimize } from './api'
import { useProfile } from './hooks/useProfile'
import { useAuth } from './context/AuthContext'
import { upsertPlan, listPlans, loadPlan, deletePlan } from './lib/plans'
import SetupForm from './components/SetupForm'
import ResultsView from './components/ResultsView'
import AuthModal from './components/AuthModal'
import PlansModal from './components/PlansModal'
import './App.css'

export default function App() {
  const [view, setView] = useState('setup')   // 'setup' | 'results'

  // ── Catalog data ─────────────────────────────────────────
  const [programs,       setPrograms]       = useState([])
  const [catalog,        setCatalog]        = useState([])
  const [apExams,        setApExams]        = useState([])
  const [apExamsLoading, setApExamsLoading] = useState(true)
  const [apExamsError,   setApExamsError]   = useState(false)

  // ── Persisted student profile (localStorage) ──────────────
  const {
    name, setName,
    selectedPrograms, setSelectedPrograms,
    manualCourses, setManualCourses,
    apEntries, setApEntries,
    savedAt,
    isReturning,
    clearProfile,
  } = useProfile()

  // ── Auth ──────────────────────────────────────────────────
  const { user, loading: authLoading, signOut } = useAuth()
  const [showAuthModal,  setShowAuthModal]  = useState(false)
  const [showPlansModal, setShowPlansModal] = useState(false)
  const [savedPlans,     setSavedPlans]     = useState([])
  const [loadingPlans,   setLoadingPlans]   = useState(false)
  const [currentPlanId,    setCurrentPlanId]    = useState(null)  // UUID of open saved plan
  const [saveStatus,       setSaveStatus]       = useState('idle') // 'idle'|'saving'|'saved'|'error'
  const [loadBanner,       setLoadBanner]       = useState(null)  // message shown after loading a plan
  const [planCourseIds,    setPlanCourseIds]    = useState([])    // selected course IDs (for saving)
  const [loadedCourseIds,  setLoadedCourseIds]  = useState(null)  // pre-fill selections on load

  // ── Optimizer result ──────────────────────────────────────
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  // Derive the full completed set: AP-resolved courses + manual courses
  const completedCourses = useMemo(() => {
    const apCourseIds = apEntries.flatMap(e => e.courses ?? [])
    return [...new Set([...apCourseIds, ...manualCourses])]
  }, [apEntries, manualCourses])

  // AP entries that award generic elective credit (no mapped UW course).
  const apGenericCredits = useMemo(() =>
    apEntries.filter(e => (e.courses ?? []).length === 0 && e.genericCredit && e.credits > 0),
    [apEntries]
  )

  // ── Fetch AP exams ────────────────────────────────────────
  const loadApExams = useCallback(() => {
    setApExamsLoading(true)
    setApExamsError(false)
    fetchApExams()
      .then(data => {
        setApExams(Array.isArray(data) ? data : [])
        setApExamsLoading(false)
      })
      .catch(() => {
        setApExamsError(true)
        setApExamsLoading(false)
      })
  }, [])

  // ── Load catalog on mount ─────────────────────────────────
  useEffect(() => {
    fetchPrograms()
      .then(setPrograms)
      .catch(() => setError('Could not load programs. Is the backend running?'))

    loadApExams()

    fetchCatalog()
      .then(setCatalog)
      .catch(() => {})
  }, [loadApExams])

  // ── Handlers: optimizer ───────────────────────────────────
  async function handleSubmit() {
    setLoading(true)
    setError(null)
    try {
      const data = await optimize(completedCourses, selectedPrograms, apGenericCredits)
      setResult(data)
      setView('results')
    } catch (err) {
      setError(err.message ?? 'Optimization failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleReoptimize(overrides = {}) {
    try {
      const data = await optimize(completedCourses, selectedPrograms, apGenericCredits, overrides)
      setResult(data)
    } catch (err) {
      console.warn('Re-optimization failed:', err.message)
    }
  }

  function handleBack() {
    setView('setup')
    setResult(null)
    setError(null)
    setLoadBanner(null)
    setLoadedCourseIds(null)
    setPlanCourseIds([])
  }

  function handleClearProfile() {
    clearProfile()
    setResult(null)
    setCurrentPlanId(null)
    setSaveStatus('idle')
    setView('setup')
  }

  // ── Handlers: save plan ───────────────────────────────────
  async function handleSavePlan() {
    if (!user) {
      setShowAuthModal(true)
      return
    }
    setSaveStatus('saving')
    try {
      // Auto-generate a plan name from the selected programs if no user name set.
      const planName = name
        ? `${name}'s Plan`
        : selectedPrograms
            .map(id => {
              if (id.includes('ds-bs'))   return 'Data Science BS'
              if (id.includes('ie-bs'))   return 'Industrial Engineering BS'
              if (id.includes('cs-bs'))   return 'CS BS'
              return id
            })
            .join(' + ') || 'My Plan'

      const saved = await upsertPlan({
        id:                   currentPlanId ?? undefined,
        name:                 planName,
        targetProgramIds:     selectedPrograms,
        completedCourseIds:   manualCourses,
        apCredits:            apEntries,
        selectedCourseIds:    planCourseIds,   // the courses the user checked off
        semesterPlan:         result,          // full optimizer result blob
      })
      setCurrentPlanId(saved.id)
      setSaveStatus('saved')
      // Reset the 'saved' badge after 3 seconds.
      setTimeout(() => setSaveStatus('idle'), 3000)
    } catch (err) {
      console.error('Save plan failed:', err)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  // ── Handlers: load plans ──────────────────────────────────
  async function handleOpenPlans() {
    if (!user) { setShowAuthModal(true); return }
    setLoadingPlans(true)
    setShowPlansModal(true)
    try {
      const plans = await listPlans()
      setSavedPlans(plans)
    } catch (err) {
      console.error('Could not load plans:', err)
      setSavedPlans([])
    } finally {
      setLoadingPlans(false)
    }
  }

  async function handleRestorePlan(planId) {
    try {
      const plan = await loadPlan(planId)

      // Restore setup inputs regardless of whether we have a saved result.
      setSelectedPrograms(plan.target_program_ids ?? [])
      setManualCourses(plan.completed_course_ids ?? [])
      setApEntries(plan.ap_credits ?? [])
      setCurrentPlanId(plan.id)

      // Restore the course selections that were checked when the plan was saved.
      setLoadedCourseIds(plan.selected_course_ids?.length ? plan.selected_course_ids : null)

      if (plan.semester_plan) {
        // Full optimizer result was saved — jump straight to results view.
        setResult(plan.semester_plan)
        setView('results')
      } else {
        // Inputs were restored but no saved result — go to setup so the
        // user can click Calculate to rebuild their plan.
        setResult(null)
        setView('setup')
        setLoadBanner('Plan restored! Your programs and courses are loaded — click Calculate to rebuild your schedule.')
      }
    } catch (err) {
      console.error('Could not load plan:', err)
      setLoadBanner(`❌ Failed to load plan: ${err.message ?? 'Unknown error'}`)
    }
  }

  async function handleDeletePlan(planId) {
    try {
      await deletePlan(planId)
      setSavedPlans(prev => prev.filter(p => p.id !== planId))
      if (currentPlanId === planId) {
        setCurrentPlanId(null)
        setSaveStatus('idle')
      }
    } catch (err) {
      console.error('Could not delete plan:', err)
    }
  }

  // ── Auth bar label ────────────────────────────────────────
  function saveBtnLabel() {
    if (saveStatus === 'saving') return '…Saving'
    if (saveStatus === 'saved')  return '✓ Saved'
    if (saveStatus === 'error')  return '✗ Error'
    return currentPlanId ? '💾 Save' : '💾 Save plan'
  }

  // ── Render ────────────────────────────────────────────────
  return (
    <div className="app">

      {/* ── Auth bar ──────────────────────────────────────── */}
      {!authLoading && (
        <div className="auth-bar">
          {!user ? (
            <button
              className="btn btn--ghost auth-bar__signin"
              onClick={() => setShowAuthModal(true)}
            >
              Sign in to save plans
            </button>
          ) : (
            <div className="auth-bar__user">
              <span className="auth-bar__email">{user.email}</span>
              {view === 'results' && result && (
                <button
                  className={`btn btn--ghost auth-bar__save ${saveStatus === 'saved' ? 'auth-bar__save--saved' : ''} ${saveStatus === 'error' ? 'auth-bar__save--error' : ''}`}
                  onClick={handleSavePlan}
                  disabled={saveStatus === 'saving'}
                >
                  {saveBtnLabel()}
                </button>
              )}
              <button className="btn btn--ghost" onClick={handleOpenPlans}>
                My plans
              </button>
              <button className="btn btn--ghost" onClick={signOut}>
                Sign out
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Load banner ───────────────────────────────────── */}
      {loadBanner && (
        <div className={`load-banner ${loadBanner.startsWith('❌') ? 'load-banner--error' : 'load-banner--info'}`}>
          <span>{loadBanner}</span>
          <button className="load-banner__close" onClick={() => setLoadBanner(null)}>×</button>
        </div>
      )}

      {/* ── Main views ────────────────────────────────────── */}
      {view === 'setup' && (
        <SetupForm
          name={name}
          onNameChange={setName}
          savedAt={savedAt}
          isReturning={isReturning}
          onClear={handleClearProfile}
          programs={programs}
          selectedPrograms={selectedPrograms}
          onProgramsChange={setSelectedPrograms}
          apExams={apExams}
          apExamsLoading={apExamsLoading}
          apExamsError={apExamsError}
          onRetryApExams={loadApExams}
          apEntries={apEntries}
          onApEntriesChange={setApEntries}
          manualCourses={manualCourses}
          onManualCoursesChange={setManualCourses}
          onSubmit={handleSubmit}
          loading={loading}
          error={error}
        />
      )}
      {view === 'results' && result && (
        <ResultsView
          result={result}
          catalog={catalog}
          onBack={handleBack}
          onReoptimize={handleReoptimize}
          onSelectionIdsChange={setPlanCourseIds}
          loadedCourseIds={loadedCourseIds}
        />
      )}

      {/* ── Modals ────────────────────────────────────────── */}
      {showAuthModal && (
        <AuthModal onClose={() => setShowAuthModal(false)} />
      )}
      {showPlansModal && (
        <PlansModal
          plans={savedPlans}
          loadingPlans={loadingPlans}
          onLoad={handleRestorePlan}
          onDelete={handleDeletePlan}
          onClose={() => setShowPlansModal(false)}
        />
      )}

    </div>
  )
}
