import { autofillBookInfo, addBook as addBookUtil } from "../../../api/books";
import { initialFormValues } from "./addbook.constants";

import { useState } from "react";

export function useAddBook() {

    const [isAutofilling, setIsAutofilling] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [bookData, setBookData] = useState(initialFormValues);

    const [toastMessage, setToastMessage] = useState("");

    async function autofill(isbn) {
       
        setBookData(prev => 
            ({...prev, ...handleLoadData("Autofilling...")}));

        setIsAutofilling(true);
        try{
            const resp = await autofillBookInfo(isbn);

            if(resp.message === "No book found") {
                setBookData(prev =>
                    ({...prev, ...handleLoadData("Unknown") }));
                setToastMessage(resp.message);
                return;
            }
    
            const date_acquired = resp.book.date_acquired.substring(0,10).trim();
    
            setBookData(prev => ({
                ...prev,
                "isbn" : isbn,
                "title" : resp.book.title,
                "author" : resp.book.author,
                "edition" : resp.book.edition,
                "description" : resp.book.description,
                "publisher" : resp.book.publisher,
                "date_acquired" : date_acquired,
                "year_published" : resp.book.year_published,
                "pages" : resp.book.pages,
                "tags" : resp.book.tags,
                "cover_url" : resp.book.cover_url
            }));

        }catch(error) {
            setToastMessage("Server Error");
            setBookData(prev => ({
                ...prev,
                ...handleLoadData("")
            }));
            return;
        }finally {
            setIsAutofilling(false);
        }
    }

    async function addBook(data, coverImage) {
        setIsSubmitting(true);

        try {
            const resp = await addBookUtil(data, coverImage);
            setToastMessage(resp.message);

            return resp;
            
        } finally {
            setIsSubmitting(false);
        }
    }

    const handleLoadData = (value = "") => 
        Object.fromEntries(
            Object.keys(initialFormValues)
                .filter(key => ![
                                "isbn",
                                "classification",
                                "accession_number",
                                "call_number",
                                "cover_url",
                            ].includes(key))
                .map(key => [key, value])
        )

    return ({ isAutofilling, isSubmitting, bookData, toastMessage, setToastMessage, setBookData, autofill, addBook });
}