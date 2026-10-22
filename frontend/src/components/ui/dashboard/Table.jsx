import styles from "../../../styles/components/dashboards/tablecontainer.module.css"

import { useLocation } from "react-router-dom"; 
import { getStorage } from "../../../pages/auth/auth.util";

import { useBorrowedBooks } from "../../../pages/user/borrowedBooks/useBorrowedBooks"
import { useBorrowers } from "../../../hooks/useBorrowers";
import { userDashboardTable, historyTable, inventoryTable } from "./table.constants";

export default function Table() {

    const { borrowedBooks } = useBorrowedBooks();
    const { allBorrowers } = useBorrowers();
    const { pathname } = useLocation();
    const isUserDashboard = pathname.endsWith("/dashboard") 

    const borrowHistory =
        allBorrowers.filter(borrower =>
            borrower.user.id_number === getStorage().getItem("id_number") &&
            !["Due", "Overdue"].includes(borrower.book.status)
        );

    const dueBooks = 
        borrowedBooks.filter(book => book.status === "Due" || book.status === "Overdue");
    
    const tableTitles = isUserDashboard
        ? userDashboardTable
        : pathname.endsWith("/inventory")
            ? inventoryTable
            :historyTable
    
    const checkDate = (date) => {
        return date ? date : "Cancelled";
    };
    
    const content = () => {
        if (isUserDashboard) {
            return (
                dueBooks.map((book, index) => (
                    <tr key={index}>
                        <td>{book.book.title}</td>
                        <td>{book.borrow_date.slice(0, 10)}</td>
                        <td>{book.due_date}</td>
                        <td>{book.status}</td>
                    </tr>
                ))
            )
        }
        
        if (pathname.endsWith("/history")) {
            return (
                borrowHistory.map((book, index) => (
                    <tr key={index}>
                        <td>{book.book.title}</td>
                        <td>{checkDate(book.borrow_date?.slice(0, 10))}</td>
                        <td>{checkDate(book.due_date)}</td>
                        <td>{book.return_date}</td>
                        <td>--</td>{/* TEMPORARY */}
                    </tr>
                ))
            )
        }

        if (pathname.endsWith("/inventory")) {
            return (
                <tr>
                    <td>ID Number</td>
                    <td>Book Title</td>
                    <td>MM/DD</td>
                    <td>Days</td>
                </tr>                
            )
        }
    }
    
    return (
        <div className={styles.container}>
            {isUserDashboard && (
                <div className={styles.header} >
                    <p>Borrowed Books Reminder</p>
                </div>
            )}
            <div className={styles.tableContainer}>
                <table>
                    <thead>
                        <tr>
                            {tableTitles.map(title => (
                                <th key={title}>{title}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {content()}
                    </tbody>
                </table>
            </div>
        </div>
    )
}