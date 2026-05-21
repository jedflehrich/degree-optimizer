import { useState, useEffect } from 'react'
import { fetchPrograms, optimize } from './api'
import SetupForm from './components/SetupForm'
import ResultsView from './components/ResultsView'
import './App.css'

/**
 * App
 * Root component. Manages two views: 'setup' and 'results'.
 * All API calls live here so child components stay pure/presentational.
 */
export default function App() {
  // View state
  const [view, setView] = useState('setup')   // 'setup' | 'results'

  // Programs
  const [programs, setPrograms] = useState([])
  const [selectedPrograms, setSelectedPrograms] = useState([])

  // Completed courses (list of course IDs)
  const [completedCourses, setCompletedCourses] = useState([])

  // Optimization result
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Load programs once on mount
  useEffect(() => {
    fetchPrograms()
      .then(setPrograms)
      .catch(() => setError('Could not load programs. Is the backend running?'))
  }, [])

  async function handleSubmit() {
    setLoading(true)
    setError(null)
    try {
      const data = await optimize(completedCourses, selectedPrograms)
      setResult(data)
      setView('results')
    } catch (err) {
      setError(err.message ?? 'Optimization failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function handleBack() {
    setView('setup')
    setResult(null)
    setError(null)
  }

  return (
    <div className="app">
      {view === 'setup' && (
        <SetupForm
          programs={programs}
          selectedPrograms={selectedPrograms}
          onProgramsChange={setSelectedPrograms}
          completedCourses={completedCourses}
          onCoursesChange={setCompletedCourses}
          onSubmit={handleSubmit}
          loading={loading}
          error={error}
        />
      )}
      {view === 'results' && result && (
        <ResultsView result={result} onBack={handleBack} />
      )}
    </div>
  )
}
