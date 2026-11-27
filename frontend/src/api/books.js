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

export async function addBook(data, coverImage){
    try {
        const formData = new FormData();

        Object.entries(data).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                if (Array.isArray(value) || typeof value === "object") {
                    formData.append(key, JSON.stringify(value));
                } else {
                    formData.append(key, value);
                }
            }
        });

        if (coverImage) {
            formData.append("cover_image", coverImage);
        }
        
        const resp = await authFetch(`${API_URL}/addBook/`, {
          method: 'POST',
          body: formData,
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

export async function getRecommendations(bookId) {
    try {
        const resp = await authFetch(`${API_URL}/getRecommendations/?book_id=${bookId}`);

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

export async function exportBorrowedBooksCSV() {
    try {
        const resp = await authFetch(`${API_URL}/exportBorrowedBooksCSV/`);

        // Errors are JSON; only a 200 carries the CSV, so it must not go through returnData.
        if (resp.status !== 200) {
            return await returnData(resp);
        }

        // Content-Disposition is only readable cross-origin if the server exposes it.
        const disposition = resp.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
        const filename = match ? decodeURIComponent(match[1].trim()) : "borrowed_books.csv";

        return ({"status": 200, "blob": await resp.blob(), filename});
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function acceptBorrowedBook(loan_id) {
    try {
        const resp = await authFetch(`${API_URL}/acceptBorrowedBook/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ loan_id })
        });
    
        return await returnData(resp)
    } catch (error) {
        return ({error, "status": 500, "message":"Connection to Server Failed"});
    }
}

export async function returnBook(loan_id) {
    try {
        const resp = await authFetch(`${API_URL}/returnBook/` , {
          method: 'PUT',
          headers: {
            'Content-Type':'application/json',
          },
          body: JSON.stringify({ loan_id })
        });

        return await returnData(resp);
    
    } catch {
        return ({"status": 500, "message":"Connection to Server Failed"});
    }
}

export async function cancelBorrowedBook(loan_id) {
    try {
        const resp = await authFetch(`${API_URL}/cancelBorrowedBook/` , {
          method: 'PUT',
          headers: {
            'Content-Type':'application/json',
          },
          body: JSON.stringify({ loan_id })
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

export async function addCopy(data){
    try {
        const resp = await authFetch(`${API_URL}/addCopy/`, {
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

export async function editCopy(data){
    try {
        const resp = await authFetch(`${API_URL}/editCopy/`, {
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

export async function removeCopy(data){
    try {
        const resp = await authFetch(`${API_URL}/removeCopy/`, {
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
