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

function getQuery(params) {
    return new URLSearchParams({
        range: params?.range.toLowerCase() ?? "",
        item_type: params?.item_type.toLowerCase() ?? "",
        program: params?.program ?? "all",
        academic_year: params?.academic_year ?? "",
        semester: params?.semester ?? "",
        education_level: params?.education_level ?? "",
    }) 
}

export async function getAdminCirculationAnalytics(params) {
    console.log(params);
    try {
        const query = getQuery(params);
        
        const resp = await authFetch(
            `${API_URL}/getCirculationDashboard?${query.toString()}`
        );

        return await returnData(resp);
    } catch (err){
        return ({"status": 500, "message":`Connection to Server Failed: ${err}`});
    }
}

export async function getAdminBorrowersAnalytics(params) {
    try {
        const query = getQuery(params);
        
        const resp = await authFetch(
            `${API_URL}/getBorrowersDashboard?${query.toString()}`
        );

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
