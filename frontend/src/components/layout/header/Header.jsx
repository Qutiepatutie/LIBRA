import styles from "../../../styles/components/layout/header.module.css"

import avatar from "../../../assets/profile-icon.png"

import { useLocation } from "react-router-dom"
import { getStorage } from "../../../pages/auth/auth.util.js"

export default function Header({ setShowUserMenu, showUserMenu}) {

    const { pathname } = useLocation();

    const currPage = {
        "/library" : "Library",
        "/borrowed-books" : "Borrowed Books",
        "/history" : "History",
        "/discussion-room-reservation" : "Discussion Room Reservation",

        "/admin/history" : "History",
        "/admin/add-book" : "Add Book",
    }

    const getPageTitle = (path) => {
        if (path.includes("dashboard")) {
            return "Dashboard";
        }

        if (path.includes("admission")) {
            return "Admission"
        }

        return currPage[path] || "";
    }

    return (
        <div className={styles.header}>
            <div className={styles.infoContainer}>
                <p className={styles.title}>{getPageTitle(pathname)}</p>
    
                <div className={styles.profile} onClick={() => setShowUserMenu(!showUserMenu)}>
                    <img className={styles.avatar} src={avatar}/>
                    <div className={styles.profileInfo}>
                        <p className={styles.userName}>{getStorage().getItem("user_firstName")}</p>
                    </div>
                </div>
            </div>
        </div>
    )
}