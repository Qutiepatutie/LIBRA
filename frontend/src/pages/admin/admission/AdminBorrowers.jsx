import styles from "../../../styles/adminPages/admission/borrowers.module.css"

import { useLocation } from "react-router-dom";

import { useState } from "react";
import { useBorrowers } from "../../../hooks/useBorrowers.js"
import { SearchBar } from "../../../components/ui/Inputs.jsx";

import ConfirmAdmission from "./ConfirmAdmission.jsx";
import BookBorrowerList from "../../../components/adminAdmission/BookBorrowerList.jsx"
import Toast from "../../../components/ui/Toast.jsx"

export default function AdminBorrowers() {
    const [query, setQuery] = useState("");
    const [confirm, setConfirm] = useState(false);
    const [borrower, setBorrower] = useState({});

    const { pathname } = useLocation();

    const category = pathname.split("/").at(-1);
    
    const {
        pendingBorrowers,
        currentBorrowers,
        loading,
        returnBook,
        cancelBook,
        acceptBook,
        searchBorrowers,
        toastMessage,
        showToast,
        showToastFunc,
    } = useBorrowers();
    
    const params = {
        borrowers: {
            data: pendingBorrowers,
            category: "Pending"
        },
        "return-books": {
            data: currentBorrowers,
            category: "Current"
        }
    }
    
    const param = params[category];
    
    const displayedData = query
        ? searchBorrowers(param.data, query)
        : param.data;

    function handleBorrower(idNum) {
        if (!idNum) return;

        if (borrower.user.id_number !== idNum) {
            showToastFunc("ID doesn't match");
            return;
        }

        if (borrower.status === "Pending") {
            acceptBook(borrower.book.id);
            
        } else {
            returnBook(borrower.book.id);
        }

        setConfirm(false);
    }
    
    return (
        <>
            <Toast message={toastMessage} show={showToast} />

            {confirm && (
                <ConfirmAdmission
                    loading={loading}
                    setConfirm={setConfirm}
                    handleBorrower={handleBorrower}
                />
            )}

            <div className={styles.bookBorrowers}>
                <div className={styles.header}>
                    <SearchBar 
                        placeholder="Search by name or ID number"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                </div>
                <div className={`
                        ${styles.listContainer}
                        ${loading ? styles.loading : ""}
                        `
                    }
                >
                    <BookBorrowerList
                        borrowers={displayedData}
                        cancelBook={cancelBook}
                        loading={loading}
                        category={param.category}
                        setConfirm={setConfirm}
                        setBorrower={setBorrower}
                    />
                </div>
            </div>
        </>
    )
}