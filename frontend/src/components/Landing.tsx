import React from 'react';

interface LandingProps {
    onStart: () => void;
}

export const Landing: React.FC<LandingProps> = ({ onStart }) => {
    return (
        <div className="text-center max-w-2xl space-y-8 animate-fade-in mx-auto">
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
                    onClick={onStart}
                    className="px-8 py-4 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow-lg shadow-brand-500/20 transition-all transform hover:-translate-y-0.5 active:translate-y-0 duration-150 text-base"
                >
                    Start Your Journey
                </button>
            </div>
        </div>
    );
};
