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

export async function getAdminCirculationAnalytics() {
    try {
        const resp = await authFetch(`${API_URL}/getCirculationDashboard`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function getAdminInventoryAnalytics() {
    try {
        const resp = await authFetch(`${API_URL}/getInventoryDashboard`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function getAdminBorrowersAnalytics() {
    try {
        const resp = await authFetch(`${API_URL}/getBorrowersDashboard`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}