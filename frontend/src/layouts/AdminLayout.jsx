import styles from "../styles/layouts/adminlayout.module.css"

import { NavLink, Outlet, useLocation } from "react-router-dom"

export default function AdminLayout() {

    const { pathname } = useLocation();
    const page = pathname.split("/")[2];
    
    const subPages = {
        dashboard: {
            "circulation": "Circulation",
            "borrowers": "Borrowers",
            "inventory": "Inventory",
        },
        admission: {
            "borrowers": "Borrowers",
            "return-books": "Return Books",
            "reserve-rooms": "Reserve Rooms",
        },
        history: {
            "books": "Books",
            "rooms": "Rooms",
        }
    }
    
    return (
            <div className={styles.page}>
                <div className={styles.container}>
                    <div className={styles.buttons}>
                    {Object.entries(subPages[page]).map(([route, label]) => (
                            <NavLink
                                key={route}
                                to={route}
                                className={({ isActive }) => isActive ? styles.active : ""}
                            >
                                {label}
                            </NavLink>
                        ))}
                    </div>

                    <div className={styles.content}>
                        <Outlet />
                    </div>
                </div>
            </div>
    )
}