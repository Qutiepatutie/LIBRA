import styles from "../../../styles/userPages/roomreservation.module.css"

import { useState, useEffect } from "react";

// import { testData } from "./test.data"

import { TextInput, Selector } from "../../../components/ui/Inputs";
import CustomButton from "../../../components/ui/CustomButton";

import { initialForm, formFields, roomSelection } from "./roomreservation.constants";

import { getStorage } from "../../auth/auth.util"

// TEST DATA
// const data = testData;

export default function Lrc1() {

    const [form, setForm] = useState(initialForm);
    
    const data = [];

    function formatTime(hour) {
        hour = String(hour);
        return `${hour.padStart(2, "0")}:00:00`;
    }
    
    const handleChange = (field, value) => {
        if (field === "room" || field === "lrc") {
            setForm(prev => ({
                ...prev,
                time: { start_time: "", end_time: "" }
            }));
        }
        
        setForm(prev => ({
            ...prev,
            [field]: value
        }))
    }

    const handleTimeChange = (hour) => {
        setForm(prev => {
            const { start_time, end_time } = prev.time;
            const formattedTime = formatTime(hour);
            
            if (formattedTime === start_time) {
                return {
                    ...prev,
                    time: {
                        start_time: "",
                        end_time: "",
                    }
                }
            }
            
            if (formattedTime === end_time) {
                return {
                    ...prev,
                    time: {
                        ...prev.time,
                        end_time: ""
                    }
                }
            }

            if (start_time === "") {
                return {
                    ...prev,
                    time: {
                        ...prev.time,
                        start_time: formattedTime,
                    }
                }
            }

            const startHour = Number(start_time?.split(":")[0])

            if (end_time === "" &&
                Math.abs(hour - startHour) <= 2) {
                    if (startHour < hour) {
                    return {
                        ...prev,
                        time: {
                            ...prev.time,
                            end_time: formattedTime,
                        }
                    }
                } else {
                    return {
                        ...prev,
                        time: {
                            start_time: formattedTime,
                            end_time: start_time, 
                        }
                    }
                }
            }

            return prev;
        })
    }

    useEffect(() => {
        console.log(form);
    }, [form]);

    useEffect(() => {
        setForm(prev => {
            const name = `${getStorage().getItem("user_firstName")} ${getStorage().getItem("user_lastName")}`;

            return {
                ...prev,
                name: name,
                id_number: getStorage().getItem("id_number"),
                program: getStorage().getItem("program"),
            }
        });
    }, [])
    
    return (
        <div className={styles.roomReservation}>
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
                            />
                        </div>
                        
                        <div className={styles.selector}>
                            <Selector
                                placeholder={"Select Room"}
                                options={roomSelection[form.lrc]}
                                value={form.room}
                                onChange={(e) => handleChange("room", e.target.value)}
                                disabled={form.lrc === ""}
                            />
                        </div>
                    </div>
                    
                    <div className={styles.slot}>
                        {
                            Array.from({ length: 14 }).map((_, timeIndex) => {
                                const slotHour = timeIndex + 7;
                                const formattedTime =
                                    `${slotHour % 12 || 12}:00 ${slotHour >= 12 ? "PM" : "AM"}`;

                                const start = form.time.start_time === ""
                                    ? null
                                    : Number(form.time.start_time?.split(":")[0]);
                                
                                const end = form.time.end_time === ""
                                    ? null
                                    : Number(form.time.end_time?.split(":")[0]);
                                
                                const isActive =
                                    start === slotHour || end === slotHour 

                                const notInRange =
                                    start !== null &&
                                    end === null &&
                                    Math.abs(slotHour - start) > 2;
                                
                                const disabled =
                                    form.room === "" || notInRange;

                                const isReserved = data.some(reservation => {
                                    const start_timeHour = Number(reservation.start_time.split(":")[0]);
                                    const end_timeHour = Number(reservation.end_time.split(":")[0]);
                                    const currRoom = Number(form.room?.split(" ")[1]);
                                    const currLrc = Number(form.lrc?.split(" ")[1]);

                                    return (
                                        reservation.room === currRoom &&
                                        reservation.lrc === currLrc &&
                                        slotHour >= start_timeHour &&
                                        slotHour < end_timeHour
                                    );
                                });
                                
                                return (
                                    <button
                                        className={`
                                            ${styles.timeButton}
                                            ${isActive ? styles.active : ""}
                                            ${isReserved ? styles.reserved : ""}
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
                    <div className={styles.form}>
                        {
                            formFields.map(({ label, name }) => {
                                return (
                                    <div key={label} className={styles.input}>
                                        <TextInput
                                            label={label}
                                            name={name}
                                            value={form[name]}
                                            disabled={form[name] ===  "Laguna"}
                                            onChange={(e) => handleChange(name, e.target.value)}
                                        />
                                    </div>
                                ) 
                            })   
                        }
                    </div>
                    
                    <div className={styles.buttons}>
                        <div className={styles.button}>
                            <CustomButton
                                onClick={() => setForm(initialForm)}
                                type={"reset"}
                                action={"clear"}
                                value={"Clear"}
                            />
                        </div>
                        
                        <div className={styles.button}>
                            <CustomButton
                                onClick={() => { }}
                                type={"button"}
                                action={"confirm"}
                                value={"Reserve"}
                            />
                        </div>
                    </div>
                </form>
            </div>
        </div>
    )
}