import styles from "../../../styles/userPages/dashboard/history.module.css"

import Table from "../../../components/ui/dashboard/Table"

export default function BorrowingHistory() {
    return (
        <div className={styles.container}>
            <div className={styles.panel}>
                <p className={styles.label}>Total Borrowed</p>
                <p className={styles.value}>0</p>
            </div>
            <div className={styles.panel}>
                <p className={styles.label}>Overdue</p>
                <p className={styles.value}>0</p>
            </div>
        
            <div className={styles.panel}>
                <p className={styles.label}>Late Returned</p>
                <p className={styles.value}>0</p>
            </div>
        
            <div className={styles.panel}>
                <p className={styles.label}>Total Fine</p>
                <p className={styles.value}>₱0</p>
            </div>
        
            <div className={`${styles.panel} ${styles.table}`}>
                <Table />
            </div>
        </div>
    )
}