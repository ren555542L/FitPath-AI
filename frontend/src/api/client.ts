// @ts-ignore
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

// Simple in-memory/localStorage token management for Guest sessions
const TOKEN_KEY = "fitpath_guest_token";
const GUEST_ID_KEY = "fitpath_guest_id";

export const getGuestToken = () => localStorage.getItem(TOKEN_KEY);
export const getGuestId = () => localStorage.getItem(GUEST_ID_KEY);

export const setGuestSession = (guestId: string, token: string) => {
    localStorage.setItem(GUEST_ID_KEY, guestId);
    localStorage.setItem(TOKEN_KEY, token);
};

export const clearGuestSession = () => {
    localStorage.removeItem(GUEST_ID_KEY);
    localStorage.removeItem(TOKEN_KEY);
};

async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
    const token = getGuestToken();
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(options.headers as Record<string, string> || {})
    };

    if (token) {
        headers["X-Guest-Token"] = token;
    }

    const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Request failed with status ${response.status}`);
    }

    return response.json();
}

export const api = {
    guest: {
        start: () => fetchWithAuth("/api/guest/start", { method: "POST" }),
        me: () => fetchWithAuth("/api/guest/me"),
        delete: () => fetchWithAuth("/api/guest", { method: "DELETE" }),
    },
    profile: {
        create: (data: any) => fetchWithAuth("/api/profile", {
            method: "POST",
            body: JSON.stringify(data)
        }),
    },
    plan: {
        generate: () => fetchWithAuth("/api/plan/generate", { method: "POST" }),
        get: () => fetchWithAuth("/api/plan"),
        delete: () => fetchWithAuth("/api/plan", { method: "DELETE" }),
    },
    dashboard: {
        get: () => fetchWithAuth("/api/dashboard"),
    },
    workouts: {
        complete: (sessionId: string) => fetchWithAuth(`/api/workouts/${sessionId}/complete`, { method: "POST" }),
    },
    checkins: {
        submit: (data: any) => fetchWithAuth("/api/checkins", {
            method: "POST",
            body: JSON.stringify(data)
        }),
    },
    reminders: {
        update: (data: any) => fetchWithAuth("/api/reminders", {
            method: "PATCH",
            body: JSON.stringify(data)
        }),
    }
};
