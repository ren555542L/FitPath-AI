import React, { useEffect, useState } from 'react';
import { api } from '../api/client';

interface PlanGenerationProps {
    onComplete: (data: any) => void;
    onSafetyBlocked: (guidance: any) => void;
}

export const PlanGeneration: React.FC<PlanGenerationProps> = ({ onComplete, onSafetyBlocked }) => {
    const [status] = useState("Generating your custom plan...");
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let mounted = true;

        const generate = async () => {
            try {
                const result = await api.plan.generate();
                
                if (!mounted) return;

                if (result.workflow_status === "completed") {
                    onComplete(result);
                } else if (result.workflow_status === "safety_blocked" || result.workflow_status === "redirected") {
                    onSafetyBlocked(result.safety_guidance);
                } else {
                    setError("Plan generation failed or was rejected by reviewers.");
                }
            } catch (err: any) {
                if (mounted) setError(err.message || "An error occurred during generation");
            }
        };

        generate();

        return () => {
            mounted = false;
        };
    }, [onComplete, onSafetyBlocked]);

    if (error) {
        return (
            <div className="max-w-xl w-full bg-white border border-red-100 shadow-xl rounded-3xl p-8 space-y-6 mx-auto text-center">
                <h2 className="text-2xl font-extrabold text-red-600">Generation Failed</h2>
                <p className="text-slate-600">{error}</p>
                <button onClick={() => window.location.reload()} className="px-5 py-2.5 bg-slate-800 text-white rounded-lg">Try Again</button>
            </div>
        );
    }

    return (
        <div className="max-w-xl w-full bg-white border border-slate-100 shadow-xl rounded-3xl p-8 space-y-6 mx-auto text-center">
            <div className="animate-pulse space-y-4">
                <div className="text-4xl">⚙️</div>
                <h2 className="text-2xl font-extrabold text-slate-900">{status}</h2>
                <p className="text-sm text-slate-500">This may take a few moments as our multi-agent workflow builds and reviews your routine.</p>
                
                <div className="w-full bg-slate-100 h-2 rounded-full mt-4 overflow-hidden">
                    <div className="bg-brand-500 h-full animate-[progress_2s_ease-in-out_infinite] w-1/2 rounded-full"></div>
                </div>
            </div>
        </div>
    );
};
