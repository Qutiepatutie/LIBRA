import styles from "../../../styles/adminPages/dashboard/inventory.module.css"

import Table from "../../../components/ui/dashboard/Table"

export default function Inventory() {
    return (
        <div className={styles.container}>
            <div className={styles.panel}>
                <p className={styles.value}>0</p>
                <p className={styles.label}>Available</p>
            </div>
            <div className={styles.panel}>
                <p className={styles.value}>0</p>
                <p className={styles.label}>Borrowed</p>
            </div>

            <div className={styles.panel}>
                <p className={styles.value}>0</p>
                <p className={styles.label}>Overdue</p>
            </div>

            <div className={styles.panel}>
                <p className={styles.value}>0</p>
                <p className={styles.label}>Lost/Damaged</p>
            </div>
            
            <div className={styles.panel}>
                <Table />
            </div>
        </div>
    )
}