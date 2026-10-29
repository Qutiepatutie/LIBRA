import styles from "../../../styles/userPages/borrowedBooks/details.module.css"

import { useState } from "react"

import { useBorrowers } from "../../../hooks/useBorrowers"

import close from "../../../assets/close-icon.svg"
import CustomButton from "../../../components/ui/CustomButton"
import ConfirmCancel from "./ConfirmCancel"

export default function Details({ setShowDetails, book, userBorrowedBooks, setUserBorrowedBooks }) {

    const [showConfirmCancel, setShowConfirmCancel] = useState(false);

    const { cancelBook } = useBorrowers();

    function handleCancel() {
        setShowDetails(false);
        setUserBorrowedBooks(
            userBorrowedBooks
                .filter(borrowedBook =>
                    borrowedBook.book.call_number !== book.call_number));
        cancelBook(book.isbn, book.call_number);
    }

    return (
        <div className={styles.backdrop} onClick={() => setShowDetails(false)}>
            <div className={styles.details} onClick={(e) => e.stopPropagation()}>
                <div
                    className={styles.close}
                    onClick={() => setShowDetails(false)}
                >
                    <img src={close} />
                </div>

                <div className={styles.coverContainer}>
                    <div className={styles.cover}>
                        <img src={book?.cover_url} />
                    </div>
                </div>
                <div className={styles.bookDetails}>
                    <div className={styles.header}>
                        <p className={styles.title}>{book?.title}</p>
                        <p className={styles.author}>By {book?.author}</p>
                    </div>
                    <div className={styles.body}>
                        <p className={`${styles.status} ${styles[book.status]}`}><span>Status:</span> {book.status}</p>
                        {book.status !== "Pending" && (
                            <>
                                <p className={styles.die}><span>Due Date:</span> {book.due_date || "--"}</p>
                                <p className={styles.fine}><span>Fine:</span> {book.status === "Overdue" ? "₱ 25" : ""}</p>
                            </>
                        )}
                    </div>

                </div>

                {book.status === "Pending" ? (
                    <div className={styles.buttonContainer}>
                        <CustomButton
                            value={"Cancel Borrow"}
                            type="button"
                            action="clear"
                            onClick={() => setShowConfirmCancel(true)}
                        />
                    </div>
                ) : (
                    <p className={styles.footer}>Please return this book on or before the due date.</p>
                )}
            </div>

            {showConfirmCancel && (
                <ConfirmCancel
                    setShowConfirmCancel={setShowConfirmCancel}
                    handleCancel={handleCancel}
                />
            )}

        </div>
    )
}
