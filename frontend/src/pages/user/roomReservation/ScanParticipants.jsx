import styles from "../../../styles/userPages/roomReservation/scanparticipants.module.css"

import { useState, useEffect} from "react";

import QRScanner from "../../../components/qr/QRScanner.jsx"
import CustomButton from "../../../components/ui/CustomButton.jsx"

import { reserveRoom } from "../../../api/rooms.js";

export default function ScanParticipants({ user, form, setForm, setConfirmReservation, setReserved }) {
    
    const [data, setData] = useState("");
    const [loading, setLoading] = useState(false);

    const min = form?.lrc === "LRC 1" ? 4 : 2;
    const max = form?.lrc === "LRC 1" ? 10 : 4;
    
    useEffect(() => {
        if (!data) return;
        
        setForm(prev => {
            const participants = prev.participants;

            if (data === user
                || participants.includes(data) 
                || participants.length === (max-1)
            ) {
                return prev;
            }

            return {
                ...prev,
                participants: [
                    ...prev["participants"],
                    data
                ]
            };
        });

        setData("");
    }, [data, user, setForm]);

    const handleRemove = (participant) => {
        setForm(prev => ({
            ...prev,
            participants: prev.participants.filter(
                person => person !== participant
            ),
        }));
    }

    const handleBack = () => {
        setForm(prev => ({...prev, participants: []}));
        setConfirmReservation(false);
    }

    const handleConfirm = async () => {
        setLoading(true);

        try {
            const resp = await reserveRoom(form);
    
            if (resp.status !== 201) {
                console.log(resp.errors);
                console.log(resp);
                return;
            }
            console.log("Success");
            console.log(resp.data);
            
            setReserved(true);
            handleBack();
        } finally {
            setLoading(false);
        }
    }

    
    return (
        <div
            className={styles.backdrop}
            onClick={() => handleBack()}
        >
            <div
                className={styles.scanParticipants}
                onClick={(e) => e.stopPropagation()}
            >
                <div className={styles.header}>
                    <p>Scan the QR codes of other participants</p>
                </div>
                <div className={styles.scannerContainer}>
                    <div className={styles.scanner}>
                        <QRScanner
                            setData={setData}
                        /> 
                    </div>
                </div>
                <div className={styles.listContainer}>
                    <div className={styles.header}>
                        <p>Participants ({form.participants.length + 1}/{max}):</p>
                        <p className={styles.subHeader}><i>Minimum of {min+1}</i></p>
                    </div>
                    <ul className={styles.list}>
                        <li>{user} (You)</li>
                        {form.participants && (
                            form.participants.map((participant) => (
                                <li key={participant}>
                                    <div className={styles.participant}>
                                        {participant}
                                        <div className={styles.button}>
                                            <CustomButton
                                                value="X"
                                                action="cancel"
                                                onClick={() => handleRemove(participant)}
                                            />
                                        </div>
                                    </div>
                                </li>
                            )))
                        }
                    </ul>
                </div>
                <div className={styles.buttons}>
                    <div className={styles.back}>
                        <CustomButton
                            value="Back"
                            onClick={() => handleBack()}
                            action="return"
                        /> 
                    </div>
                    
                    <div className={styles.reserve}>
                        <CustomButton
                            value="Finish Reservation"
                            disabled={form.participants.length < min || loading}
                            onClick={() => handleConfirm()}
                        /> 
                    </div>

                </div>
            </div>
        </div>
    )
}