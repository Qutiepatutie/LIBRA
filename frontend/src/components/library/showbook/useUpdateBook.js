import { useState } from "react";
import { borrowBook as borrowBookUtil, editBook as editBookUtil } from "../../../api/books";
import { getStorage } from "../../../pages/auth/auth.util";

export function useUpdateBook(setShowConfirm, notify) {
    
    const [loading, setLoading] = useState(false);
    const [toastMessage, setToastMessage] = useState("");

    const [isEdit, setIsEdit] = useState(false);

    async function editBook(bookDetails) {
        
        const resp = await editBookUtil({ ...bookDetails, book_id: bookDetails.id });
        
        if(resp.status !== 200) {
            setToastMessage(resp.message);
            return;
        }

        setToastMessage("Successfully edited book");
        setIsEdit(false);
    }

    async function borrowBook(book) {
        const data = {
            book_id: book.id,
            id_number: getStorage().getItem("id_number")
        }

        setLoading(true);
        const resp = await borrowBookUtil(data);
        setToastMessage(resp.message);
        setLoading(false);

        if(resp.status === 200) {
            setShowConfirm(false)
        }
        notify()
    }

    return { loading, toastMessage, isEdit,setIsEdit, setToastMessage, borrowBook, editBook };
}