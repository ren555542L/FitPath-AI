import { useState, useEffect } from 'react'
import { Landing } from './components/Landing'
import { Onboarding } from './components/Onboarding'
import { PlanGeneration } from './components/PlanGeneration'
import { PlanScreen } from './components/PlanScreen'
import { Dashboard } from './components/Dashboard'
import { SafetyScreen } from './components/SafetyScreen'
import { CheckInModal } from './components/CheckInModal'
import { api, getGuestToken, setGuestSession, clearGuestSession } from './api/client'

type Page = 'landing' | 'onboarding' | 'generating' | 'safety' | 'dashboard' | 'plan';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('landing')
  const [safetyGuidance, setSafetyGuidance] = useState<any>(null)
  const [planData, setPlanData] = useState<any>(null)
  const [traceEvents, setTraceEvents] = useState<any[]>([])
  const [isCheckInOpen, setIsCheckInOpen] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)

  // Initialization
  useEffect(() => {
    const init = async () => {
      const token = getGuestToken();
      if (token) {
        try {
          const guestInfo = await api.guest.me();
          if (guestInfo.profile) {
            // Check if they have an active plan
            try {
              await api.plan.get();
              setCurrentPage('dashboard');
            } catch (e) {
              // No plan, they have a profile, could be generating or safety blocked
              // for simplicity, send to onboarding
              setCurrentPage('onboarding');
            }
          } else {
            setCurrentPage('onboarding');
          }
        } catch (e) {
          clearGuestSession();
          setCurrentPage('landing');
        }
      }
      setIsInitializing(false);
    };
    init();
  }, []);

  const handleStartGuest = async () => {
    try {
      const guest = await api.guest.start();
      setGuestSession(guest.guest_id, guest.guest_token);
      setCurrentPage('onboarding');
    } catch (e) {
      alert("Failed to start guest session.");
    }
  };

  const handleResetData = async () => {
    try {
      await api.guest.delete();
      clearGuestSession();
      setCurrentPage('landing');
    } catch (e) {
      alert("Failed to reset data.");
    }
  };

  if (isInitializing) {
    return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between">
      {/* Header */}
      <header className="bg-white border-b border-slate-100 py-4 px-6 sticky top-0 z-50 shadow-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">🌱</span>
            <span className="font-bold text-slate-800 text-xl tracking-tight">FitPath</span>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-xs px-2.5 py-1 bg-brand-50 text-brand-700 font-medium rounded-full border border-brand-100">
              {currentPage === 'dashboard' ? 'Active Plan' : 'Guest Mode'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl mx-auto w-full py-12 px-6 flex flex-col items-center justify-center">
        {currentPage === 'landing' && (
          <Landing onStart={handleStartGuest} />
        )}

        {currentPage === 'onboarding' && (
          <Onboarding 
            onBack={handleResetData}
            onComplete={(safetyStatus) => {
              if (safetyStatus === 'medical_review_required' || safetyStatus === 'general_fitness_redirect') {
                setSafetyGuidance({
                  safety_status: safetyStatus,
                  title: 'Safety Check',
                  message: 'Based on your profile, we recommend consulting a physician before starting a new routine.',
                  can_proceed: false
                });
                setCurrentPage('safety');
              } else {
                setCurrentPage('generating');
              }
            }}
          />
        )}

        {currentPage === 'generating' && (
          <PlanGeneration 
            onComplete={(result) => {
              setPlanData(result.fitness_plan);
              setTraceEvents(result.trace_events || []);
              setCurrentPage('plan');
            }}
            onSafetyBlocked={(guidance) => {
              setSafetyGuidance(guidance);
              setCurrentPage('safety');
            }}
          />
        )}

        {currentPage === 'plan' && (
          <PlanScreen 
            plan={planData}
            traceEvents={traceEvents}
            onGoToDashboard={() => setCurrentPage('dashboard')}
          />
        )}

        {currentPage === 'safety' && (
          <SafetyScreen 
            guidance={safetyGuidance}
            onReset={handleResetData}
          />
        )}

        {currentPage === 'dashboard' && (
          <Dashboard 
            onCheckIn={() => setIsCheckInOpen(true)}
            onReset={handleResetData}
            onViewPlan={async () => {
              try {
                const result = await api.plan.get();
                setPlanData(result);
                // In a real app we might also fetch trace_events, but for MVP fetching plan is enough
                setTraceEvents([]);
                setCurrentPage('plan');
              } catch (err) {
                alert("Failed to load plan");
              }
            }}
          />
        )}
      </main>

      {isCheckInOpen && (
        <CheckInModal 
          onClose={() => setIsCheckInOpen(false)}
          onSubmit={() => {
            setIsCheckInOpen(false);
            // Dashboard will reload itself via a prop trigger or polling, but
            // for MVP, we just force reload the dashboard component by unmounting and remounting or passing a key.
            // A simpler way: window.location.reload()
            window.location.reload();
          }}
        />
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-slate-100 py-6 px-6 text-center text-slate-400 text-xs">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-2">
          <span>&copy; {new Date().getFullYear()} FitPath AI. All rights reserved.</span>
          <span className="bg-slate-100 px-2 py-1 rounded">Developer Demo Mode Active</span>
        </div>
      </footer>
    </div>
  )
}

export default App
