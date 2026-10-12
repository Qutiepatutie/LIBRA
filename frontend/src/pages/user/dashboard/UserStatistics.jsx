import styles from "../../../styles/userPages/dashboard/statistics.module.css"

import Table from "./Table.jsx"

import LineGraph from "../../../components/ui/graphs/Line.jsx"
import BarGraph from "../../../components/ui/graphs/Bar.jsx"

export default function UserStatistics() {
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
                <p className={styles.label}>Due this week</p>
                <p className={styles.value}>0</p>
            </div>
        
            <div className={styles.panel}>
                <p className={styles.label}>Fine</p>
                <p className={styles.value}>₱0</p>
            </div>

            <div className={`${styles.panel} ${styles.doughnutGraphContainer}`}>
                <LineGraph
                    header={"My Borrowing Frequency"}
                    data={[]}
                />
            </div>
            
            <div className={`${styles.panel} ${styles.barGraphContainer}`}>
                <BarGraph
                    header={"Most Borrowed Subjects"}
                    subHeader={"Based on your history"}
                    data={[]}
                />
            </div>
        
            <div className={`${styles.panel} ${styles.books}`}>
                <Table />
            </div>
        </div>
    )
}