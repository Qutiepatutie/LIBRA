import { logout, getStorage, getAccessToken, getRefreshToken } from "../pages/auth/auth.util.js";

const API_URL = import.meta.env.VITE_API_URL;

export async function returnData(resp) {
    const data = await resp.json();
    const status = resp.status;
    
    return ({
        "status": status,
        ...data,
    });
}

export async function authFetch(url, options = {}) {
    let access = getAccessToken();
    const refresh = getRefreshToken();

    if (!refresh) {
        logout();
        throw new Error("No refresh token");
    }

    let response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            Authorization: `Bearer ${access}`
        },
    });

    if (response.status !== 401) {
        return response;
    }

    const refreshResponse = await fetch(`${API_URL}/token/refresh/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            refresh,
        })
    });

    if (!refreshResponse.ok) {
        logout();
        throw new Error("Session Expired");
    }

    const data = await refreshResponse.json();

    getStorage().setItem("access", data.access);

    const resp = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            Authorization: `Bearer ${data.access}`,
        },
    });

    return resp;
}

export async function login(email, pass) {
    try {
        const response = await fetch(`${API_URL}/login/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email,
                password: pass
            })
        });

        return await returnData(response);
        
    } catch {
        return ({"status": 500, "message":"Server Connection Error"});
   }
}

export async function googleLogin(code) {
    try {
        const response = await fetch(`${API_URL}/google/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code })
        });

        return await returnData(response);

    } catch {
        return ({"status": 500, "message":"Server Connection Error"});
    }
}

export async function changePass(email, newPass){
    try {
        const response = await fetch(`${API_URL}/changePass/`, {
            method: 'POST',
            headers: {
               'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email,
                newPass: newPass
            })
        });
        
        return await returnData(response);

    } catch (error) {
        console.log(error);
        return ({"status": 500, "message":"Server Connection Error"});
    }
}

export async function register(data){
    try {
        const response = await fetch(`${API_URL}/register/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        return await returnData(response);
        
    } catch {
        return ({"status": 500 ,"message":"Server Connection Error"});
    }
}