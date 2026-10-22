import { useState, useEffect, useMemo } from "react";

import { getAllBorrowers, acceptBorrowedBook, returnBook as returnBookUtil, cancelBorrowedBook} from "../api/books";
import { getBookStatus } from "../utils/getBookStatus";

export function useBorrowers() {

    const [allBorrowers, setAllBorrowers] = useState([]);
    const [toastMessage, setToastMessage] = useState("");
    const [showToast, setShowToast] = useState(false);
    const [loading, setLoading] = useState(false);
    
    useEffect(() => {
        const fetchBorrowers = async () => {
            const fetchedBorrowers = await getAllBorrowers();

            setAllBorrowers(fetchedBorrowers.data);
        }

        fetchBorrowers();
    }, []);

    const pendingBorrowers = useMemo(() => 
        allBorrowers.filter(b => b.status === "Pending"),
        [allBorrowers]
    );

    const currentBorrowers = useMemo(() => 
        allBorrowers.filter(borrower => 
            borrower.status !== "Pending" 
            && borrower.status !== "Returned"
            && borrower.status !== "Cancelled"
                ).map(borrower => ({
                    ...borrower,
                    status: getBookStatus(borrower),
                })),
        [allBorrowers]
    );
    
    function showToastFunc(message) {
        setToastMessage(message);
        
        // Show toast for 3 seconds
        setShowToast(() => {
            const timer = setTimeout(() => {
                setShowToast(false);
                setToastMessage("");
            }, 3000); // 3 seconds
    
            return () => clearTimeout(timer);
        });
    }

    async function returnBook(isbn, call_num) {
        setLoading(true);
        const resp = await returnBookUtil(isbn, call_num);
        setLoading(false);
            
        showToastFunc(resp.message);

        if(resp.status === "failed") { return; }

        setAllBorrowers(borrowers => 
            borrowers.filter(b => b.book.isbn !== isbn)
        );
    }
    
    async function cancelBook(isbn, call_num) {
        setLoading(true);
        const resp = await cancelBorrowedBook(isbn, call_num);
        setLoading(false);
            
        showToastFunc(resp.message);

        if(resp.status === "failed") { return; }

        setAllBorrowers(borrowers => 
            borrowers.filter(b => b.book.isbn !== isbn)
        );
    }

    async function acceptBook(isbn, call_num) {
        setLoading(true);
        const resp = await acceptBorrowedBook(isbn, call_num);
        setLoading(false);
        console.log(resp);

        showToastFunc(resp.message);

        if (resp.status !== 200)
            return;

        setAllBorrowers(borrowers => 
            borrowers.map(b => 
                b.book.isbn === isbn 
                && b.book.call_number === call_num 
                && b.status !== "Returned"
                && b.status !== "Cancelled"
                ? {
                    ...b,
                    status: resp.book.status,
                    due_date: resp.book.due_date,
                }
                : b
            )
        );
    }

    const searchBorrowers = (list, query) =>
        list.filter( b => 
            `${b.user.first_name} ${b.user.last_name} ${b.user.id_number}`
            .toLowerCase()
            .includes(query)
        );

    return {
        toastMessage,
        showToast,
        loading,
        pendingBorrowers,
        currentBorrowers,
        allBorrowers,
        setAllBorrowers,
        returnBook,
        acceptBook,
        cancelBook,
        searchBorrowers
    };
}