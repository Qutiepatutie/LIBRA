import styles from "../../../styles/adminPages/dashboard/borrowers.module.css"

import Header from "./DashboardHeader"

import LineGraph from "../../../components/ui/dashboard/graphs/Line.jsx"
import BarGraph from "../../../components/ui/dashboard/graphs/Bar.jsx"
import DoughnutGraph from "../../../components/ui/dashboard/graphs/Doughnut.jsx"

export default function Borrowers() {
    return (
        <div className={styles.borrowers}>
            <Header/>
            <div className={styles.container}>
                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Total Registered Students</p>
                </div>
                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Avg. Loan Duration</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Active Borrowers</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Inactive Borrowers</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Avg. Checkouts per borrower</p>
                </div>
                
                <div className={styles.panel}>
                    <BarGraph
                        header={"Top 10 most borrowed books"}
                        subHeader={"Ranked by checkouts"}
                        data={[]}
                    />
                </div>

                <div className={styles.panel}>
                    <DoughnutGraph
                        header={"Active vs Inactive users"}
                            subHeader={"Inactive means no checkouts in the selected semester"}
                        data={[]}
                    />
                </div>
                
                <div className={styles.panel}>
                    <LineGraph
                        header={"Borrowing frequency overtime"}
                        subHeader={"By hour of day"}
                        data={[]}
                    />
                </div>
                
            </div>
        </div>
    )
}