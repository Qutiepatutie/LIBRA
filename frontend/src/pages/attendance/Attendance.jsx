import styles from "../../styles/attendance/attendance.module.css"

import { useState, useEffect} from "react"

import QRScanner from "../../components/qr/QRScanner.jsx"
import CustomButton from "../../components/ui/CustomButton.jsx";

import MessagePopUp from "./MessagePopUp.jsx"

import { logout } from "../auth/auth.util.js";

export default function Attendance() {

    const [id, setId] = useState("");
    const [idInput, setIdInput] = useState("");
    const [invalidId, setInvalidId] = useState(false);

    useEffect(() => {
        if (!id) return;
        
        if (id === "logout") {
            logout();
            return;
        }
        
        const timer = setInterval(() => {
            setId("");
        }, 3000);
        return () => clearInterval(timer);
    }, [id]);

    function onSubmit(e) {
        e.preventDefault();
        
        if (!idInput) return;
        
        if (!/^\d{11}$/.test(idInput)) {
            setInvalidId(true);
            return;
        }

        setId(idInput);
        setIdInput("");
    }
     
    return (
        <>
            {(id && id !== "logout") && (
                <MessagePopUp
                    id={id}
                />
            )}
            <div className={styles.container}>
                <div className={styles.header}>
                <p className={styles.main}>Welcome to LRC VI-A SRB2</p>
                <p className={styles.sub}>Scan your QR or manually enter your Student ID</p>
                </div>
                <div className={styles.content}>
                <div className={styles.scannerContainer}>
                    <div className={styles.scanner}>
                            <QRScanner
                                setData={setId}
                            />
                        </div>
                        <div className={styles.inputContainer}>
                            <form onSubmit={(e) => onSubmit(e)} className={styles.input}>
                                <input
                                    value={idInput}
                                    onChange={(e) => {
                                        setIdInput(e.target.value);
                                        setInvalidId(false);
                                    }}
                                    placeholder={"06XXXXXXXXX"}
                                    maxLength={11}
                                    type="text"
                                    inputMode="numeric"
                                    pattern="[0-9]*"
                                />
                                <div className={styles.button}>
                                    <CustomButton
                                        value={"➤"}
                                    />
                                </div>
                            </form>
                            
                            <p className={`${styles.message} ${invalidId ? "" : styles.hidden}`}>
                                Invalid ID
                            </p>
                        </div>
                </div>
                </div>
            </div>
        </>
    )
}