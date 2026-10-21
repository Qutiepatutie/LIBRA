import styles from "../../../styles/adminPages/admission/borrowers.module.css"

import RoomReservationList from "../../../components/adminAdmission/RoomReservationList.jsx"

import { useState } from "react";
import { SearchBar } from "../../../components/ui/Inputs";
import { useBorrowers } from "../../../hooks/useBorrowers";

import Toast from "../../../components/ui/Toast";

export default function RoomReservations() {
    const [currentQuery, setCurrentQuery] = useState("");
    
    const {
        currentBorrowers,
        loading,
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
            <div className={styles.bookBorrowers}>
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
                    <RoomReservationList
                        borrowers={[]}
                    /> 
                </div>
            </div>
        </>
    )
}