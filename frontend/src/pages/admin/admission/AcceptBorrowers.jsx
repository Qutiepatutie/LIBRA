import styles from "../../../styles/adminPages/admission/bookborrowers.module.css"

import { useState } from "react";
import { useBorrowers } from "../../../hooks/useBorrowers"

import BorrowerList from "../../../components/adminDashboard/BorrowerList.jsx"
import { SearchBar } from "../../../components/ui/Inputs";

import Toast from "../../../components/ui/Toast.jsx"

export default function Borrowers() {

    const [pendingQuery, setPendingQuery] = useState("");
    
    const {
        pendingBorrowers,
        loading,
        updateBookStatus,
        acceptBook,
        searchBorrowers,
        toastMessage,
        showToast,
    } = useBorrowers();
    
    const displayedPending = pendingQuery
        ? searchBorrowers(pendingBorrowers, pendingQuery)
        : pendingBorrowers;
    
    return (
        <>
            <Toast message={toastMessage} show={showToast} />
            <div className={styles.bookBorrowers}>
                <div className={styles.header}>
                    <SearchBar 
                        placeholder="Search by name or ID number"
                        name="pending"
                        value={pendingQuery}
                        onChange={(e) => setPendingQuery(e.target.value)}
                    />
                </div>
                <div className={`
                        ${styles.listContainer}
                        ${loading ? styles.loading : ""}
                        `
                    }
                >
                    <BorrowerList
                        borrowers={displayedPending}
                        updateBookStatus={updateBookStatus}
                        acceptBook={acceptBook}
                        loading={loading}
                        category={"Pending"}
                    />
                </div>
            </div>
        </>
    )
}