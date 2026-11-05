import styles from "../../../styles/userPages/roomReservation/roomreservation.module.css"

import { useState, useEffect } from "react";

// import { testData } from "./test.data"

import ScanParticipants from "./ScanParticipants";

import { Selector } from "../../../components/ui/Inputs";
import CustomButton from "../../../components/ui/CustomButton";
import Toast from "../../../components/ui/Toast";

import { initialForm, roomSelection, departments } from "./roomreservation.constants";

import { getStorage } from "../../auth/auth.util"
import { getUserReservedRooms } from "../../../api/rooms";
import { useBorrowers } from "../../../hooks/useBorrowers";

// TEST DATA
// const data = testData;

export default function RoomReservation() {

    const [form, setForm] = useState(initialForm);
    const [confirmReservation, setConfirmReservation] = useState(false);
    const [reserved, setReserved] = useState(false);

    const { allReservations } = useBorrowers();
    
    function formatTime(hour) {
        hour = String(hour);
        return `${hour.padStart(2, "0")}:00:00`;
    }
    
    const handleChange = (field, value) => {
        if (field === "room" || field === "lrc") {
            setForm(prev => ({
                ...prev,
                start_time: "",
                end_time: ""
            }));
        }

        if (field === "lrc") {
            setForm(prev => ({
                ...prev,
                room: "",
            }))
        }
        
        setForm(prev => ({
            ...prev,
            [field]: value
        }))
    }

    const handleClear = () => {
        setForm(prev => ({
            ...prev,
            lrc: "",
            room: "",
            start_time: "",
            end_time: ""
        }));
    }

    const handleTimeChange = (hour) => {
        setForm(prev => {
            const { start_time, end_time } = prev;
            const formattedTime = formatTime(hour);
            
            if (formattedTime === start_time) {
                return {
                    ...prev,
                    start_time: "",
                    end_time: "",
                }
            }
            
            if (formattedTime === end_time) {
                return {
                    ...prev,
                    end_time: ""
                }
            }

            if (start_time === "") {
                return {
                    ...prev,
                    start_time: formattedTime,
                }
            }

            const startHour = Number(start_time?.split(":")[0])

            if (end_time === "" &&
                Math.abs(hour - startHour) <= 2) {
                    if (startHour < hour) {
                    return {
                        ...prev,
                        end_time: formattedTime,
                    }
                } else {
                    return {
                        ...prev,
                        start_time: formattedTime,
                        end_time: start_time, 
                    }
                }
            }

            return prev;
        })
    }

    const handleReserve = () => {

        const { room, lrc, start_time, end_time } = form;

        if (!lrc) {
            console.log("please choose an lrc");
            return;
        }
        if (!room) {
            console.log("please choose a room");
            return;
        }
        if (!start_time) {
            console.log("please choose a starting time");
            return;
        }
        if (!end_time) {
            console.log("please choose an ending time");
            return;
        }

        
        setForm(prev => ({
            ...prev,
            participants: [
                ...prev["participants"],
            ]
        }))
        
        setConfirmReservation(true);
    }

    useEffect(() => {
        setForm(prev => {
            const name = `${getStorage().getItem("user_firstName")} ${getStorage().getItem("user_lastName")}`;
            
            return {
                ...prev,
                name: name,
                id_number: getStorage().getItem("id_number"),
                program: getStorage().getItem("program"),
                department: departments.find(dept => dept.programs.includes(getStorage().getItem("program")))?.department,
            }
        });
    }, [])

    useEffect(() => {
        console.log(form);
    }, [form])

    useEffect(() => {
        async function fetch() {
            const resp = await getUserReservedRooms();
            console.log(resp.data);
            
            if (resp.data.length) {
                setReserved(true);

                const { start_time, end_time, lrc, room } = resp.data[0];
                
                setForm(prev => ({
                    ...prev,
                    lrc,
                    room,
                    start_time,
                    end_time,
                }))
            }
        }

        fetch();
    }, []);
    
    return (
        <div className={styles.roomReservation}>
            {confirmReservation &&
                <ScanParticipants
                    user={form.id_number}
                    form={form}
                    setForm={setForm}
                    setConfirmReservation={setConfirmReservation}
                    setReserved={setReserved}
                />
            }
            <div className={styles.container}>
                <div className={styles.header}>
                    <p>Schedule a Discussion Room</p>
                </div>
                <div className={styles.timeTableContainer}>
                    <p className={styles.text}><i>Maximum of 2 hours only</i></p>
                    
                    <div className={styles.buttons}>
                        <div className={styles.selector}>
                            <Selector
                                placeholder={"Select LRC"}
                                options={["LRC 1", "LRC 2"]}
                                value={form.lrc}
                                onChange={(e) => handleChange("lrc", e.target.value)}
                                disabled={reserved}
                            />
                        </div>
                        
                        <div className={styles.selector}>
                            <Selector
                                placeholder={"Select Room"}
                                options={roomSelection[form.lrc]}
                                value={form.room}
                                onChange={(e) => handleChange("room", e.target.value)}
                                disabled={form.lrc === "" || reserved}
                            />
                        </div>
                    </div>
                    
                    <div className={styles.slot}>
                        {
                            Array.from({ length: 14 }).map((_, timeIndex) => {
                                const slotHour = timeIndex + 7;
                                const formattedTime =
                                    `${slotHour % 12 || 12}:00 ${slotHour >= 12 ? "PM" : "AM"}`;

                                const start = form.start_time === ""
                                    ? null
                                    : Number(form.start_time?.split(":")[0]);
                                
                                const end = form.end_time === ""
                                    ? null
                                    : Number(form.end_time?.split(":")[0]);
                                
                                const isActive =
                                    start === slotHour || end === slotHour 

                                const notInRange =
                                    start !== null &&
                                    end === null &&
                                    Math.abs(slotHour - start) > 2;
                                
                                const disabled =
                                    form.room === "" || notInRange || reserved;

                                const isReserved = allReservations.some(reservation => {
                                    // console.log(reservation);
                                    const start_timeHour = Number(reservation.start_time.split(":")[0]);
                                    const end_timeHour = Number(reservation.end_time.split(":")[0]);

                                    return (
                                        reservation.room === form.room &&
                                        reservation.lrc === form.lrc &&
                                        slotHour >= start_timeHour &&
                                        slotHour < end_timeHour &&
                                        (reservation.status === "Pending" ||
                                        reservation.status === "Active")
                                    );
                                });
                                
                                return (
                                    <button
                                        className={`
                                            ${styles.timeButton}
                                            ${isActive ? styles.active : ""}
                                            ${(isReserved && !reserved) ? styles.reserved : ""}
                                        `}
                                        key={slotHour}
                                        disabled={disabled || isReserved}
                                        onClick={() => handleTimeChange(slotHour)}
                                    >
                                        {formattedTime}
                                    </button>
                                )
                            })
                        }
                    </div>
                </div>
    
                <form className={styles.formContainer}>
                    
                    <div className={styles.buttons}>
                        <div className={styles.button}>
                            <CustomButton
                                onClick={() => {
                                    handleClear();
                                }}
                                type={"reset"}
                                action={"clear"}
                                value={"Clear"}
                                disabled={reserved}
                            />
                        </div>
                        
                        <div className={styles.button}>
                            <CustomButton
                                onClick={() => handleReserve()}
                                type={"button"}
                                action={"confirm"}
                                value={"Reserve"}
                                disabled={reserved}
                            />
                        </div>
                    </div>
                </form>
            </div>
        </div>
    )
}