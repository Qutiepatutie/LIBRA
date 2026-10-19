import styles from "../../styles/components/layout/bottomnav.module.css"

import { NavLink, useLocation } from "react-router-dom"

import dashboard from "../../assets/sidebar/dashboard.svg"
import library from "../../assets/sidebar/library.svg"
import borrowedBooks from "../../assets/sidebar/borrowedBooks.svg"
import history from "../../assets/sidebar/history.svg"
import addBook from "../../assets/sidebar/addbook-icon.svg"
import discussionRoom from "../../assets/sidebar/discussion-room.svg"

import { getStorage } from "../../pages/auth/auth.util.js"

export default function Sidebar() {
    const role = getStorage().getItem("role");

    const location = useLocation();
    
    const isDashboardActive =
        role === "admin"
            ? location.pathname.startsWith("/admin/dashboard")
            : location.pathname.startsWith("/dashboard")

    return (
        <>
            <div className={styles.bottomNav}>
                <div className={styles.buttons}>
                    <NavLink
                        to = {role === "admin" ? "/admin/dashboard/circulation" : "/dashboard"}
                        className={`${styles.navButton} ${isDashboardActive ? styles.active : ""}`}
                    >
                        <img className={styles.icon} src={dashboard} />
                    </NavLink>
                    
                    <NavLink
                        to = "/library"
                        className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                    >
                        <img className={styles.icon} src={library} />
                    </NavLink>
                    
                    <NavLink
                        to = {role === "admin" ? "/admin/borrowers" : "/borrowed-books"}
                        className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                    >
                        <img className={styles.icon} src={borrowedBooks} />
                    </NavLink>
                    
                    <NavLink
                        to = "/history"
                        className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                    >
                        <img className={styles.icon} src={history} />
                    </NavLink>
                    
                    <NavLink
                        to="/room-reservation"
                        className={({ isActive }) => `${styles.navButton} ${isActive ? styles.active : ""}`}
                    >
                        <img className={styles.icon} src={discussionRoom} />
                    </NavLink>
                    
                    {role === "admin" &&
                         <NavLink 
                              to = "/admin/add-book"
                              className={({isActive}) => `${styles.navButton} ${isActive? styles.active : ""}`}
                         >
                              <img className={styles.icon} src={addBook} />
                         </NavLink>
                    }
                </div>
            </div>
        </>
    )
}