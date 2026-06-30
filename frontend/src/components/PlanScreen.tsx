import React, { useState } from 'react';

interface PlanScreenProps {
    plan: any;
    traceEvents: any[];
    onGoToDashboard: () => void;
}

export const PlanScreen: React.FC<PlanScreenProps> = ({ plan, traceEvents, onGoToDashboard }) => {
    const [showActivity, setShowActivity] = useState(false);

    if (!plan || !plan.week_1) {
        return (
            <div className="text-center space-y-4">
                <p>No plan data available.</p>
                <button onClick={onGoToDashboard} className="px-4 py-2 bg-brand-600 text-white rounded-lg">Go to Dashboard</button>
            </div>
        );
    }

    return (
        <div className="max-w-4xl w-full mx-auto space-y-8">
            <div className="bg-white border border-slate-100 shadow-sm rounded-2xl p-6 md:p-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Your New Plan is Ready</h2>
                    <p className="text-sm text-slate-500 mt-1">Review your Week 1 schedule below.</p>
                </div>
                <button 
                    onClick={onGoToDashboard}
                    className="px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow-lg transition-all"
                >
                    Go to Dashboard
                </button>
            </div>

            <div className="space-y-6">
                <h3 className="text-xl font-bold text-slate-800">Week 1 Schedule</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {plan.week_1.days.map((day: any, idx: number) => (
                        <div key={idx} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
                            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
                                <h4 className="font-bold text-slate-800 text-lg">{day.day}</h4>
                                <span className={`text-xs px-2 py-1 rounded-full font-semibold ${day.is_rest ? 'bg-slate-100 text-slate-600' : 'bg-brand-50 text-brand-700 border border-brand-100'}`}>
                                    {day.is_rest ? 'Rest' : day.focus}
                                </span>
                            </div>
                            
                            {!day.is_rest && (
                                <div className="space-y-4">
                                    <p className="text-sm font-medium text-slate-700">Duration: {day.total_duration_mins} mins</p>
                                    <div className="space-y-3">
                                        {day.exercises.map((ex: any, eIdx: number) => (
                                            <div key={eIdx} className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                                                <div className="flex justify-between items-start">
                                                    <h5 className="font-bold text-slate-800">{ex.name}</h5>
                                                    <span className="text-xs text-slate-500">{ex.duration_mins}m</span>
                                                </div>
                                                {(ex.sets || ex.reps) && (
                                                    <p className="text-xs text-brand-600 font-medium mt-1">
                                                        {ex.sets ? `${ex.sets} sets` : ''} {ex.sets && ex.reps ? 'x' : ''} {ex.reps ? `${ex.reps} reps` : ''}
                                                    </p>
                                                )}
                                                
                                                {ex.instructions && ex.instructions.length > 0 && (
                                                    <ul className="text-xs text-slate-600 mt-2 list-disc pl-4 space-y-0.5">
                                                        {ex.instructions.map((inst: string, i: number) => <li key={i}>{inst}</li>)}
                                                    </ul>
                                                )}
                                                {ex.safety_note && (
                                                    <div className="mt-2 text-xs bg-amber-50 text-amber-800 p-2 rounded flex items-start gap-2">
                                                        <span>⚠️</span>
                                                        <span>{ex.safety_note}</span>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {day.is_rest && (
                                <p className="text-sm text-slate-500 italic">Active recovery or total rest day. Listen to your body.</p>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            <div className="bg-white border border-slate-100 shadow-sm rounded-2xl overflow-hidden">
                <button 
                    onClick={() => setShowActivity(!showActivity)}
                    className="w-full p-4 flex justify-between items-center bg-slate-50 hover:bg-slate-100 transition-colors"
                >
                    <span className="font-bold text-slate-700">Agent Activity Details</span>
                    <span>{showActivity ? '▲' : '▼'}</span>
                </button>
                {showActivity && (
                    <div className="p-4 bg-slate-900 text-green-400 font-mono text-xs overflow-x-auto max-h-96 overflow-y-auto space-y-2">
                        {traceEvents && traceEvents.length > 0 ? (
                            traceEvents.map((evt: any, idx: number) => (
                                <div key={idx} className="pb-2 border-b border-slate-800 last:border-0">
                                    <div className="font-bold text-slate-300">[{evt.step}]</div>
                                    <div className="text-slate-400 mt-1">{JSON.stringify(evt.details, null, 2)}</div>
                                </div>
                            ))
                        ) : (
                            <p>No trace events recorded.</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
