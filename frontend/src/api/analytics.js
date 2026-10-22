import { authFetch, returnData } from "./users";

const API_URL = import.meta.env.VITE_API_URL;

export async function getUserAnalytics() {
    try {
        const resp = await authFetch(`${API_URL}/getUserAnalytics`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}