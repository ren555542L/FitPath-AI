import React, { useState } from 'react';
import { api } from '../api/client';

interface CheckInModalProps {
    onClose: () => void;
    onSubmit: () => void;
}

export const CheckInModal: React.FC<CheckInModalProps> = ({ onClose, onSubmit }) => {
    const [completedSessions, setCompletedSessions] = useState(0);
    const [energyLevel, setEnergyLevel] = useState(3);
    const [difficultyRating, setDifficultyRating] = useState(3);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await api.checkins.submit({
                completed_sessions: completedSessions,
                energy_level: energyLevel,
                difficulty_rating: difficultyRating,
                week_number: 1 // MVP hardcoded
            });
            onSubmit();
        } catch (err: any) {
            setError(err.message || "Failed to submit check-in");
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-6">
                <div className="flex justify-between items-center">
                    <h2 className="text-xl font-bold text-slate-800">Weekly Check-in</h2>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600">✕</button>
                </div>
                
                {error && <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg">{error}</div>}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Sessions Completed this Week</label>
                        <input type="number" min="0" max="7" value={completedSessions} onChange={e => setCompletedSessions(Number(e.target.value))} className="w-full p-2 border rounded" required />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Energy Level (1-5)</label>
                        <input type="range" min="1" max="5" value={energyLevel} onChange={e => setEnergyLevel(Number(e.target.value))} className="w-full" />
                        <div className="flex justify-between text-xs text-slate-500">
                            <span>Exhausted (1)</span>
                            <span>Energized (5)</span>
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Workout Difficulty (1-5)</label>
                        <input type="range" min="1" max="5" value={difficultyRating} onChange={e => setDifficultyRating(Number(e.target.value))} className="w-full" />
                        <div className="flex justify-between text-xs text-slate-500">
                            <span>Too Easy (1)</span>
                            <span>Too Hard (5)</span>
                        </div>
                    </div>
                    
                    <div className="pt-4 flex justify-end space-x-3">
                        <button type="button" onClick={onClose} className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium">Cancel</button>
                        <button type="submit" disabled={submitting} className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-bold disabled:opacity-50">
                            {submitting ? "Submitting..." : "Submit to Coach"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};
