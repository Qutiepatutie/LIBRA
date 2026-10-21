import styles from "../../styles/adminPages/admission/borrowerlist.module.css"

import CustomButton from "../ui/CustomButton.jsx"

import roomIcon from "../../assets/pages/admin/admission/roomAdmission.svg"

export default function RoomReservationList({ borrowers, loading }) {
    
    // FOR TESTING
    // borrowers = [
    //     {
    //         user: {
    //             first_name: "Ralph Andre",
    //             last_name: "Layosa",
    //             id_number: "06230002160",
    //         },
    //         due_date: "10/21/2026",
    //         status: "Pending",
    //         room: "Room 1",
    //         lrc: "LRC 1",
    //         time: {
    //             start: "8:00:00",
    //             end: "10:00:00",
    //         }
    //     },
    // ]

    const formatTime = (time) => {
        const hour = time.split(":")[0];
        return `${hour % 12 || 12}:00 ${hour >= 12 ? "PM" : "AM"}`;
    }
    
    return (
        <div className={styles.list} >
            {borrowers.length === 0
                ? <p className={styles.noBorrowers}>No Current Reservations</p>
                : borrowers.map((borrower, index) => (
                    <div key={index} className={styles.panel}>
                        <div className={styles.itemContainer}>
                            <p className={styles.room}>{borrower.room}</p>
                            <img src={roomIcon} />
                            <p className={styles.lrc}>{borrower.lrc}</p>
                        </div>
                        <div className={styles.borrowerInfo}>
                            <p>Time: {formatTime(borrower.time.start)} - {formatTime(borrower.time.end)}</p>
                            <p>Name: {borrower.user.first_name} {borrower.user.last_name}</p>
                            <p>ID: {borrower.user.id_number}</p>
                        </div>

                        <div className={styles.buttons}>
                            {borrower.status === "Pending" &&
                                <div className={styles.cancel}>
                                    <CustomButton
                                        value="X"
                                        action="clear"
                                        onClick={() => {}}
                                        disabled={loading}
                                    />
                                </div>
                            }
                            <div className={styles.accept}>
                                <CustomButton
                                    value={"Reserve"}
                                    onClick={() => {}}
                                    action={loading ? "loading" : ""}
                                />
                            </div>
                        </div>
                    </div>
                ))
            }
        </div>
    )
}