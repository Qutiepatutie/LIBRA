import { authFetch, returnData } from "./users";

const API_URL = import.meta.env.VITE_API_URL;

export async function autofillBookInfo(isbn) {
    try {
        const resp = await authFetch(`${API_URL}/autofill/?isbn=${isbn}`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function addBook(data){
    try {
        const resp = await authFetch(`${API_URL}/addBook/`, {
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

export async function getBooks() {
    try {
        const resp = await authFetch(`${API_URL}/getBooks/`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function editBook(data){
    try {
        const resp = await authFetch(`${API_URL}/editBook/`, {
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

export async function removeBook(data){
    try {
        const resp = await authFetch(`${API_URL}/removeBook/`, {
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

export async function getAllBorrowers() {
    try {
        const resp = await authFetch(`${API_URL}/getAllBorrowedBooks/`);

        return await returnData(resp);
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function acceptBorrowedBook(book_id) {
    try {
        const resp = await authFetch(`${API_URL}/acceptBorrowedBook/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ book_id })
        });
    
        return await returnData(resp)
    } catch (error) {
        return ({error, "status": 500, "message":"Connection to Server Failed"});
    }
}

export async function returnBook(book_id) {
    try {
        const resp = await authFetch(`${API_URL}/returnBook/` , {
          method: 'PUT',
          headers: {
            'Content-Type':'application/json',
          },
          body: JSON.stringify({ book_id })
        });

        return await returnData(resp);
    
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function cancelBorrowedBook(book_id) {
    try {
        const resp = await authFetch(`${API_URL}/cancelBorrowedBook/` , {
          method: 'PUT',
          headers: {
            'Content-Type':'application/json',
          },
          body: JSON.stringify({ book_id })
        });

        return await returnData(resp);
    
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function borrowBook(data){
    try {
        const resp = await authFetch(`${API_URL}/borrowBook/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data)
        });

        return await returnData(resp)
        
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}