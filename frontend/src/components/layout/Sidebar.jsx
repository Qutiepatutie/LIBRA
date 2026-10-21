import styles from "../../styles/components/layout/sidebar.module.css"

import { NavLink, useLocation } from "react-router-dom"

import logo from "../../assets/libra-logo.png"
import dashboard from "../../assets/sidebar/dashboard.svg"
import library from "../../assets/sidebar/library.svg"
import borrowedBooks from "../../assets/sidebar/borrowedBooks.svg"
import history from "../../assets/sidebar/history.svg"
import addBook from "../../assets/sidebar/addbook-icon.svg"
import discussionRoom from "../../assets/sidebar/discussion-room.svg"
import admission from "../../assets/sidebar/admission.svg"

import { getStorage } from "../../pages/auth/auth.util.js"

export default function Sidebar() {
    const role = getStorage().getItem("role");

    const location = useLocation();
    
    const isDashboardActive =
        role === "admin"
            ? location.pathname.startsWith("/admin/dashboard")
            : location.pathname.startsWith("/dashboard")

    const isAdmissionActive = location.pathname.startsWith("/admin/admission")
    const isHistoryActive = location.pathname.startsWith("/admin/history")

    return (
        <div className={styles.sidebar}>
            <div className={styles.header}>
                <img className={styles.logo} src={logo} />
            </div>
            <div className={styles.buttons}>
                <NavLink
                    to = {role === "admin" ? "/admin/dashboard/circulation" : "/dashboard"}
                    className={`${styles.navButton} ${isDashboardActive ? styles.active : ""}`}
                >
                    <img className={styles.icon} src={dashboard} />
                    <p className={styles.tooltip}>Dashboard</p>
                </NavLink>
                
                {role === "admin" && (
                    <NavLink 
                        to = "admin/admission/borrowers"
                        className={`${styles.navButton} ${isAdmissionActive ? styles.active : ""}`}
                    >
                        <img className={styles.icon} src={admission} />
                        <p className={styles.tooltip}>Admission</p>
                    </NavLink>
                )}
                
                <NavLink
                    to = "/library"
                    className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                >
                    <img className={styles.icon} src={library} />
                    <p className={styles.tooltip}>Library</p>                    
                </NavLink>
                
                {role !== "admin" && (
                    <NavLink
                        to = "/borrowed-books"
                        className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                    >
                        <img className={styles.icon} src={borrowedBooks} />
                        <p className={styles.tooltip}>{role === "admin" ? "History" : "Borrowed Books"}</p>
                    </NavLink>
                )}
                

                {role !== "admin" && (
                    <>
                        <NavLink
                            to = "/history"
                            className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                        >
                            <img className={styles.icon} src={history} />
                            <p className={styles.tooltip}>History</p>                    
                        </NavLink>
                        
                        <NavLink
                            to="/room-reservation"
                            className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                        >
                            <img className={styles.icon} src={discussionRoom} />
                            <p className={styles.tooltip}>Room Reservation</p>
                        </NavLink>
                    </>
                )}
                {role === "admin" && (
                    <>
                        <NavLink
                            to = "admin/history/books"
                            className={`${styles.navButton} ${isHistoryActive ? styles.active : ""}`}
                        >
                            <img className={styles.icon} src={history} />
                            <p className={styles.tooltip}>History</p>                    
                        </NavLink>
                        
                        <NavLink 
                            to = "/admin/add-book"
                            className={({isActive}) => `${styles.navButton} ${isActive? styles.active : ""}`}
                        >
                            <img className={styles.icon} src={addBook} />
                            <p className={styles.tooltip}>Add Book</p>
                        </NavLink>
                    </>
                )}
            </div>
        </div>
    )
}