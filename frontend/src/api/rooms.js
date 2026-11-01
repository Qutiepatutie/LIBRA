import { authFetch, returnData } from "./users";

const API_URL = import.meta.env.VITE_API_URL;

export async function reserveRoom(data){
    try {
        const resp = await authFetch(`${API_URL}/reserveRoom/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data)
        });

        return await returnData(resp);
      
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function acceptReservedRoom(data){
    try {
        const resp = await authFetch(`${API_URL}/acceptReservedRoom/`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data)
        });

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function cancelReservedRoom(data){
    try {
        const resp = await authFetch(`${API_URL}/cancelReservedRoom/`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data)
        });

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function getAllReservedRooms() {
    try {
        const resp = await authFetch(`${API_URL}/getAllReservedRooms/`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function getUserReservedRooms() {
    try {
        const resp = await authFetch(`${API_URL}/getUserReservedRooms/`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}