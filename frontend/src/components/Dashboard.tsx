import React, { useEffect, useState } from 'react';
import { api } from '../api/client';

interface DashboardProps {
    onCheckIn: () => void;
    onReset: () => void;
    onViewPlan: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onCheckIn, onReset, onViewPlan }) => {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadDashboard = async () => {
        try {
            const result = await api.dashboard.get();
            setData(result);
        } catch (err: any) {
            setError(err.message || "Failed to load dashboard");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadDashboard();
    }, []);

    const handleCompleteWorkout = async (sessionId: string) => {
        try {
            await api.workouts.complete(sessionId);
            loadDashboard();
        } catch (err: any) {
            alert("Failed to complete workout: " + err.message);
        }
    };

    const toggleReminder = async () => {
        if (!data) return;
        try {
            await api.reminders.update({
                reminder_enabled: !data.reminder_enabled,
                reminder_time: data.reminder_time || "08:00"
            });
            loadDashboard();
        } catch (err: any) {
            alert("Failed to update reminder");
        }
    };

    if (loading) return <div className="text-center p-8">Loading dashboard...</div>;
    if (error) return <div className="text-center p-8 text-red-600">{error}</div>;
    if (!data) return null;

    return (
        <div className="w-full max-w-4xl space-y-8 mx-auto">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2">
                        <h2 className="text-2xl font-bold text-slate-800">Your Dashboard</h2>
                        {data.execution_mode === 'mock' && (
                            <span className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded-full font-bold uppercase">Demo Mode</span>
                        )}
                    </div>
                    <p className="text-sm text-slate-500">Track your weekly routines and active consistency streaks.</p>
                </div>
                <div className="flex gap-2 self-start md:self-auto">
                    <button
                        onClick={onViewPlan}
                        className="px-4 py-2 text-xs font-semibold text-brand-600 bg-brand-50 hover:bg-brand-100 rounded-lg border border-brand-100 transition-colors"
                    >
                        View My Week 1 Plan
                    </button>
                    <button
                        onClick={onReset}
                        className="px-4 py-2 text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 rounded-lg border border-red-100 transition-colors"
                    >
                        Reset Data
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-2">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Active Streak</span>
                    <div className="text-3xl font-extrabold text-slate-800">{data.workout_streak || 0} Days</div>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-2">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Plan Progress</span>
                    <div className="text-3xl font-extrabold text-slate-800">{data.plan_days_progress_pct || 0}%</div>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-2">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Week 1 Completion</span>
                    <div className="text-3xl font-extrabold text-slate-800">{data.week_completion_pct || 0}%</div>
                    <p className="text-xs text-slate-500">{data.week_completed_sessions || 0} of {data.week_total_sessions || 0}</p>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm space-y-2">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Consistency Score</span>
                    <div className="text-3xl font-extrabold text-slate-800 font-mono">{data.weekly_consistency_score || "0.0"}</div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
                    <h3 className="font-bold text-slate-800 mb-4">Next Workout</h3>
                    {data.next_workout ? (
                        <div className="bg-brand-50 border border-brand-100 rounded-xl p-4">
                            <h4 className="font-bold text-brand-800">{data.next_workout.day_name} - Week {data.next_workout.week_number}</h4>
                            <p className="text-sm text-brand-600 mt-1">Est. {data.next_workout.estimated_duration_mins} mins</p>
                            <button 
                                onClick={() => handleCompleteWorkout(data.next_workout.session_id)}
                                className="mt-4 w-full bg-brand-600 text-white font-bold py-2 rounded-lg hover:bg-brand-700"
                            >
                                Mark as Completed
                            </button>
                        </div>
                    ) : (
                        <p className="text-sm text-slate-500">No upcoming workouts pending for this week.</p>
                    )}
                </div>

                <div className="space-y-6">
                    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="font-bold text-slate-800">Weekly Check-In</h3>
                            <button onClick={onCheckIn} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg text-sm">
                                Submit Check-In
                            </button>
                        </div>
                        {data.latest_adjustment ? (
                            <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 text-sm space-y-2">
                                <p><strong>Coach says:</strong> {data.latest_adjustment.recommendation}</p>
                                <p className="text-slate-600">{data.latest_adjustment.reasoning}</p>
                                {data.latest_adjustment.next_week_modifications?.length > 0 && (
                                    <ul className="list-disc pl-4 text-slate-600">
                                        {data.latest_adjustment.next_week_modifications.map((m: string, i: number) => <li key={i}>{m}</li>)}
                                    </ul>
                                )}
                            </div>
                        ) : (
                            <p className="text-sm text-slate-500">Submit a weekly check-in to get coach feedback.</p>
                        )}
                    </div>

                    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex justify-between items-center">
                        <div>
                            <h3 className="font-bold text-slate-800">Reminders</h3>
                            <p className="text-sm text-slate-500">
                                {data.reminder_enabled ? `Active for ${data.reminder_time}` : 'Currently disabled'}
                            </p>
                        </div>
                        <button 
                            onClick={toggleReminder}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${data.reminder_enabled ? 'bg-brand-600' : 'bg-slate-200'}`}
                        >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${data.reminder_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};
