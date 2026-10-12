import styles from "../../../styles/adminPages/admission/returnbooks.module.css"

import { useState } from "react";
import { useBorrowers } from "../../../hooks/useBorrowers";

import { SearchBar } from "../../../components/ui/Inputs";
import BorrowerList from "../../../components/adminDashboard/BorrowerList.jsx"

import Toast from "../../../components/ui/Toast.jsx"

export default function Inventory() {
    const [currentQuery, setCurrentQuery] = useState("");
    
    const {
        currentBorrowers,
        loading,
        updateBookStatus,
        searchBorrowers,
        toastMessage,
        showToast,
    } = useBorrowers();
    
    const displayedCurrent = currentQuery
        ? searchBorrowers(currentBorrowers, currentQuery)
        : currentBorrowers;
    
    return (
        <>
            <Toast message={toastMessage} show={showToast} />
            <div className={styles.returnBooks}>
                <div className={styles.carouselHeader}>
                    <SearchBar 
                        placeholder="Search by name or ID number"
                        name="current"
                        value={currentQuery}
                        onChange={(e) => setCurrentQuery(e.target.value)}
                    />
                </div>
                <div className={`
                        ${styles.listContainer}
                        ${loading ? styles.loading : ""}
                        `
                    }
                >
                    <BorrowerList
                        borrowers={displayedCurrent}
                        updateBookStatus={updateBookStatus}
                        loading={loading}
                        category={"Current"}
                    />
                </div>
            </div>
        </>
    )
}