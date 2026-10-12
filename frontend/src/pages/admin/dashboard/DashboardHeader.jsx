import styles from "../../../styles/adminPages/dashboard/dashboardheader.module.css" 

import { useState } from "react"

import { Selector } from "../../../components/ui/Inputs"

export default function Header() {

    const [active, setActive] = useState("day");

    const handleClick = (btn) => {
        if (btn === active) return;
        console.log(btn);
        setActive(btn);
    }
    
    return (
        <div className={styles.header}>
            <div className={styles.selectors}>
                <div className={styles.selector}>
                    <Selector
                        label="Item Type"
                        height="1.5em"
                        value=""
                        options={[]}
                        onChange={() => { }}
                    />
                </div>
                
                <div className={styles.selector}>
                    <Selector
                        label="Term"
                        height="1.5em"
                        value=""
                        options={[]}
                        onChange={() => { }}
                    />
                </div>
                
                <div className={styles.selector}>
                    <Selector
                        label="Program"
                        height="1.5em"
                        value=""
                        options={[]}
                        onChange={() => { }}
                    />
                </div>
                
                <div className={styles.selector}>
                    <Selector
                        label="Semester Term"
                        height="1.5em"
                        value=""
                        options={[]}
                        onChange={() => { }}
                    />
                </div>
            </div>
            
            <div className={styles.filters}>
                <button
                    className={ "day" === active ? styles.active : ""}
                    onClick={() => handleClick("day")}
                >
                    Day
                </button>
                <button
                    className={ "week" === active ? styles.active : ""}
                    onClick={() => handleClick("week")}
                >
                    Week
                </button>
                <button
                    className={ "semester" === active ? styles.active : ""}
                    onClick={() => handleClick("semester")}
                >
                    Semester
                </button>
                <button
                    className={ "year" === active ? styles.active : ""}
                    onClick={() => handleClick("year")}
                >
                    Year
                </button>
            </div>
        </div>
    ) 
}