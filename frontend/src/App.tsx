import { useState } from 'react'

function App() {
  const [currentPage, setCurrentPage] = useState<'landing' | 'onboarding' | 'dashboard'>('landing')

  return (
    <div className="min-height-screen bg-slate-50 flex flex-col justify-between">
      {/* Header */}
      <header className="bg-white border-b border-slate-100 py-4 px-6 sticky top-0 z-50 shadow-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">🌱</span>
            <span className="font-bold text-slate-800 text-xl tracking-tight">FitPath</span>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-xs px-2.5 py-1 bg-brand-50 text-brand-700 font-medium rounded-full border border-brand-100">
              Guest Mode
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl mx-auto w-full py-12 px-6 flex flex-col items-center justify-center">
        {currentPage === 'landing' && (
          <div className="text-center max-w-2xl space-y-8 animate-fade-in">
            <div className="space-y-4">
              <span className="text-xs uppercase tracking-widest text-brand-600 font-semibold px-3 py-1 bg-brand-50 rounded-full border border-brand-100">
                Safety-First AI fitness concierge
              </span>
              <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                Get fitter for life — <br/>
                <span className="text-brand-600">not bulkier for show.</span>
              </h1>
              <p className="text-lg text-slate-600 leading-relaxed">
                Build healthy daily habits, improve posture, stamina, and daily flexibility. 
                Custom home workouts created specifically for your age, equipment, and actual comfort level. 
                No strict diets, no bodybuilding jargon, and no high-intensity injury risks.
              </p>
            </div>

            <div className="bg-emerald-50/50 border border-emerald-100 rounded-2xl p-6 text-left flex items-start space-x-4">
              <span className="text-2xl mt-0.5">🛡️</span>
              <div>
                <h4 className="font-bold text-slate-800 text-sm">Our Safety Commitment</h4>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                  FitPath does not support bodybuilding requests or push unsafe physical limits. All plans incorporate 
                  strict rest schedules, equipment matching, and deterministic safety checks for injury or medical flags.
                </p>
              </div>
            </div>

            <div>
              <button 
                onClick={() => setCurrentPage('onboarding')}
                className="px-8 py-4 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow-lg shadow-brand-500/20 transition-all transform hover:-translate-y-0.5 active:translate-y-0 duration-150 text-base"
              >
                Start Your Journey
              </button>
            </div>
          </div>
        )}

        {currentPage === 'onboarding' && (
          <div className="max-w-xl w-full bg-white border border-slate-100 shadow-xl rounded-3xl p-8 space-y-6">
            <div className="space-y-2 text-center">
              <h2 className="text-2xl font-extrabold text-slate-900">Your Onboarding Profile</h2>
              <p className="text-sm text-slate-500">Let's build a plan tailored to your lifestyle and daily targets.</p>
            </div>
            
            <div className="p-4 bg-amber-50 border border-amber-100 text-amber-800 text-xs rounded-xl flex items-start space-x-3">
              <span className="text-lg">⚠️</span>
              <p className="leading-relaxed">
                <strong>Disclaimer:</strong> FitPath is an educational wellness planner. It is not a medical tool 
                and cannot treat, diagnose, or advise on chronic injuries or medical conditions.
              </p>
            </div>

            <div className="flex justify-between pt-4 border-t border-slate-100">
              <button 
                onClick={() => setCurrentPage('landing')}
                className="px-5 py-2.5 text-sm font-semibold text-slate-600 hover:text-slate-800 border border-slate-200 rounded-lg"
              >
                Back
              </button>
              <button 
                onClick={() => setCurrentPage('dashboard')}
                className="px-5 py-2.5 text-sm font-semibold bg-brand-600 text-white rounded-lg hover:bg-brand-700"
              >
                Next Step (Demo)
              </button>
            </div>
          </div>
        )}

        {currentPage === 'dashboard' && (
          <div className="w-full max-w-4xl space-y-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Welcome Back, Guest!</h2>
                <p className="text-sm text-slate-500">Track your weekly routines and active consistency streaks.</p>
              </div>
              <button
                onClick={() => setCurrentPage('landing')}
                className="self-start md:self-auto px-4 py-2 text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 rounded-lg border border-red-100 transition-colors"
              >
                Reset Data (Demo)
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-2">
                <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Active Streak</span>
                <div className="text-3xl font-extrabold text-slate-800">0 Days</div>
                <p className="text-xs text-slate-500">Complete your next session to start your streak.</p>
              </div>
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-2">
                <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Completion Rate</span>
                <div className="text-3xl font-extrabold text-slate-800">0%</div>
                <p className="text-xs text-slate-500">0 of 0 sessions completed.</p>
              </div>
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-2">
                <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Weekly Consistency</span>
                <div className="text-3xl font-extrabold text-slate-800 font-mono">0.0</div>
                <p className="text-xs text-slate-500">Based on regular check-ins.</p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-100 py-6 px-6 text-center text-slate-400 text-xs">
        <div className="max-w-6xl mx-auto">
          &copy; {new Date().getFullYear()} FitPath AI. All rights reserved. Made with care for daily functional life fitness.
        </div>
      </footer>
    </div>
  )
}

export default App
