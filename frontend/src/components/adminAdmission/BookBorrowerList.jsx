import styles from "../../styles/adminPages/admission/borrowerlist.module.css"

import BookPanel from "../library/BookPanel.jsx"
import CustomButton from "../ui/CustomButton.jsx"

export default function BookBorrowerList({ borrowers, cancelBook, loading, category, setConfirm, setBorrower }) {

    return (
        <div className={styles.list} >
            {borrowers.length === 0
                ? <p className={styles.noBorrowers}>No {category} Borrowers</p>
                : borrowers.map((borrower, index) => (
                    <div key={index} className={styles.panel}>
                        <div className={styles.itemContainer}>
                            <BookPanel
                                book={borrower.book}
                                hover={false}
                            />
                        </div>
                        <div className={styles.borrowerInfo}>
                            <p>{borrower.user.first_name} {borrower.user.last_name}</p>
                            <p>ID: {borrower.user.id_number}</p>
                            {borrower.due_date &&
                                <p>Due: {borrower.due_date}</p>
                            }
                        </div>

                        <div className={styles.buttons}>
                            {borrower.status === "Pending" &&
                                <div className={styles.cancel}>
                                    <CustomButton
                                        value="X"
                                        action="clear"
                                        onClick={() => cancelBook(borrower.book.id)}
                                        disabled={loading}
                                    />
                                </div>
                            }
                            <div className={styles.accept}>
                                <CustomButton
                                    value={borrower.status === "Pending"
                                        ? "Accept"
                                        : "Return"
                                    }
                                    onClick={() => {
                                        setBorrower(borrower);
                                        setConfirm(true);
                                    }}
                                />
                            </div>
                        </div>
                    </div>
                ))
            }
        </div>
    )
}
