import React, { useState } from 'react';
import { api } from '../api/client';

interface OnboardingProps {
    onBack: () => void;
    onComplete: (safetyStatus: string) => void;
}

export const Onboarding: React.FC<OnboardingProps> = ({ onBack, onComplete }) => {
    const [goal, setGoal] = useState("general wellness");
    const [fitnessLevel, setFitnessLevel] = useState("beginner");
    const [durationDays, setDurationDays] = useState(30);
    const [availableTimeMins, setAvailableTimeMins] = useState(30);
    const [daysPerWeek, setDaysPerWeek] = useState(3);
    const [equipment, setEquipment] = useState<string[]>(["No equipment"]);
    const [preferredDays, setPreferredDays] = useState<string[]>(["Monday", "Wednesday", "Friday"]);
    const [notes, setNotes] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const toggleEquipment = (eq: string) => {
        setEquipment(prev => prev.includes(eq) ? prev.filter(e => e !== eq) : [...prev, eq]);
    };

    const toggleDay = (day: string) => {
        setPreferredDays(prev => prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        if (preferredDays.length === 0) {
            setError("Please select at least one preferred day.");
            return;
        }

        setIsSubmitting(true);
        try {
            const response = await api.profile.create({
                goal,
                fitness_level: fitnessLevel,
                duration_days: durationDays,
                available_time_mins: availableTimeMins,
                days_per_week: daysPerWeek,
                equipment: equipment.length > 0 ? equipment : ["No equipment"],
                preferred_days: preferredDays,
                notes: notes || undefined
            });
            onComplete(response.safety_status);
        } catch (err: any) {
            setError(err.message || "Failed to save profile");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="max-w-xl w-full bg-white border border-slate-100 shadow-xl rounded-3xl p-8 space-y-6 mx-auto">
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

            {error && (
                <div className="p-4 bg-red-50 border border-red-100 text-red-800 text-xs rounded-xl">
                    {error}
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Goal</label>
                    <input type="text" value={goal} onChange={e => setGoal(e.target.value)} required className="w-full p-2 border rounded" placeholder="e.g. general wellness, flexibility" />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Fitness Level</label>
                        <select value={fitnessLevel} onChange={e => setFitnessLevel(e.target.value)} className="w-full p-2 border rounded">
                            <option value="beginner">Beginner</option>
                            <option value="intermediate">Intermediate</option>
                            <option value="advanced">Advanced</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Duration (Days)</label>
                        <select value={durationDays} onChange={e => setDurationDays(Number(e.target.value))} className="w-full p-2 border rounded">
                            <option value={30}>30 Days</option>
                            <option value={60}>60 Days</option>
                            <option value={90}>90 Days</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Time per session (mins)</label>
                        <input type="number" value={availableTimeMins} onChange={e => setAvailableTimeMins(Number(e.target.value))} min={10} max={180} required className="w-full p-2 border rounded" />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Days per week</label>
                        <input type="number" value={daysPerWeek} onChange={e => setDaysPerWeek(Number(e.target.value))} min={2} max={6} required className="w-full p-2 border rounded" />
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Equipment Available</label>
                    <div className="flex flex-wrap gap-2">
                        {["No equipment", "Resistance bands", "Dumbbells", "Yoga mat"].map(eq => (
                            <button key={eq} type="button" onClick={() => toggleEquipment(eq)} className={`px-3 py-1 text-xs rounded-full border ${equipment.includes(eq) ? 'bg-brand-100 border-brand-300 text-brand-800' : 'bg-white border-slate-200 text-slate-600'}`}>
                                {eq}
                            </button>
                        ))}
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Preferred Days</label>
                    <div className="flex flex-wrap gap-2">
                        {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map(day => (
                            <button key={day} type="button" onClick={() => toggleDay(day)} className={`px-3 py-1 text-xs rounded-full border ${preferredDays.includes(day) ? 'bg-brand-100 border-brand-300 text-brand-800' : 'bg-white border-slate-200 text-slate-600'}`}>
                                {day.substring(0, 3)}
                            </button>
                        ))}
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Any medical conditions or injuries? (Optional)</label>
                    <textarea value={notes} onChange={e => setNotes(e.target.value)} className="w-full p-2 border rounded h-24" placeholder="Describe any concerns here. Our safety agent will review this." />
                </div>

                <div className="flex justify-between pt-4 border-t border-slate-100">
                    <button 
                        type="button"
                        onClick={onBack}
                        disabled={isSubmitting}
                        className="px-5 py-2.5 text-sm font-semibold text-slate-600 hover:text-slate-800 border border-slate-200 rounded-lg"
                    >
                        Back
                    </button>
                    <button 
                        type="submit"
                        disabled={isSubmitting}
                        className="px-5 py-2.5 text-sm font-semibold bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
                    >
                        {isSubmitting ? 'Saving...' : 'Generate Plan'}
                    </button>
                </div>
            </form>
        </div>
    );
};
