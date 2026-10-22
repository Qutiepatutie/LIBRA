import styles from "../../../styles/adminPages/admission/borrowers.module.css"

import { useLocation } from "react-router-dom";

import { useState } from "react";
import { useBorrowers } from "../../../hooks/useBorrowers.js"
import { SearchBar } from "../../../components/ui/Inputs.jsx";

import BookBorrowerList from "../../../components/adminAdmission/BookBorrowerList.jsx"
import Toast from "../../../components/ui/Toast.jsx"

export default function AdminBorrowers() {
    const [query, setQuery] = useState("");

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
    
    return (
        <>
            <Toast message={toastMessage} show={showToast} />
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
                        returnBook={returnBook}
                        cancelBook={cancelBook}
                        acceptBook={acceptBook}
                        loading={loading}
                        category={param.category}
                    />
                </div>
            </div>
        </>
    )
}