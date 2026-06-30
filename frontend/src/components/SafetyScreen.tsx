import React from 'react';

interface SafetyScreenProps {
    guidance: {
        safety_status: string;
        title: string;
        message: string;
        can_proceed: boolean;
    };
    onReset: () => void;
}

export const SafetyScreen: React.FC<SafetyScreenProps> = ({ guidance, onReset }) => {
    return (
        <div className="max-w-xl w-full bg-white border border-red-100 shadow-xl rounded-3xl p-8 space-y-6 mx-auto text-center">
            <div className="text-4xl">⚠️</div>
            <h2 className="text-2xl font-extrabold text-slate-900">{guidance.title}</h2>
            <p className="text-slate-600 bg-red-50 p-4 rounded-xl border border-red-100">
                {guidance.message}
            </p>
            <div className="pt-4">
                <button 
                    onClick={onReset}
                    className="px-5 py-2.5 bg-slate-800 text-white rounded-lg hover:bg-slate-700"
                >
                    Start Over
                </button>
            </div>
        </div>
    );
};
