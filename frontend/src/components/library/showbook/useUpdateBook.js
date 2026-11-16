import { useState } from "react";
import {
    borrowBook as borrowBookUtil,
    editBook as editBookUtil,
    removeBook as removeBookUtil,
    addCopy as addCopyUtil,
    editCopy as editCopyUtil,
    removeCopy as removeCopyUtil
} from "../../../api/books";
import { getStorage } from "../../../pages/auth/auth.util";

export function useUpdateBook(setShowConfirm, setShowRemove, notify) {
    
    const [loading, setLoading] = useState(false);
    const [toastMessage, setToastMessage] = useState("");

    const [isEdit, setIsEdit] = useState(false);

    async function editBook(bookDetails) {
        
        // Copy data (condition, copies, counts) is edited through editCopy, not editBook.
        const titleFields = { ...bookDetails };
        ["copies", "total_copies", "available_copies", "condition", "date_acquired"]
            .forEach(key => delete titleFields[key]);
        const resp = await editBookUtil({ ...titleFields, book_id: bookDetails.id });
        
        if(resp.status !== 200) {
            setToastMessage(resp.message);
            return;
        }

        setToastMessage("Successfully edited book");
        setIsEdit(false);
    }

    async function removeBook(bookId) {
        setLoading(true);
        const resp = await removeBookUtil({book_id: bookId});
        setToastMessage(resp.message);
        setLoading(false);

        if(resp.status === 200) {
            setShowRemove(false);
        }

        notify();
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

        return resp;
    }

    // Copy actions return the response so the caller can refresh its data.
    async function copyAction(action, data) {
        setLoading(true);
        const resp = await action(data);
        setToastMessage(resp.message);
        setLoading(false);
        notify();

        return resp;
    }

    const addCopy = (data) => copyAction(addCopyUtil, data);
    const editCopy = (data) => copyAction(editCopyUtil, data);
    const removeCopy = (data) => copyAction(removeCopyUtil, data);

    return { loading, toastMessage, isEdit,setIsEdit, setToastMessage, borrowBook, editBook, removeBook, addCopy, editCopy, removeCopy };
}