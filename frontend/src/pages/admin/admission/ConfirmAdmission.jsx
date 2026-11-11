import styles from "../../../styles/adminPages/admission/confirmadmission.module.css"

import { useState, useEffect } from "react";

import QRScanner from "../../../components/qr/QRScanner.jsx"
import CustomButton from "../../../components/ui/CustomButton.jsx"

export default function ConfirmAdmission({ loading, setConfirm, handleBorrower }) {
    const [id, setId] = useState(""); 

    useEffect(() => {
        if (!id) return;
        
        handleBorrower(id);
    }, [id])
    
    return (
        <div className={styles.backdrop} onClick={() => setConfirm(false)}>
            <div className={styles.container} onClick={(e) => e.stopPropagation()}>
                <div className={styles.header}>
                    <p>Scan QR to confirm</p>
                </div>

                <div className={styles.scannerContainer}>
                    <div className={styles.scanner}>
                        <QRScanner
                           setData={setId} 
                        />
                        {loading && (
                            <div className={styles.wait}>
                                <p>Please wait...</p>
                            </div>
                        )}
                    </div>
                </div>
                
                <div className={styles.buttonContainer}>
                    <div className={styles.button}>
                        <CustomButton
                            value={"Cancel"}
                            action={"clear"}
                            onClick={() => setConfirm(false)}
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}