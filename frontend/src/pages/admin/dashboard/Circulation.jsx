import styles from "../../../styles/adminPages/dashboard/circulation.module.css" 

import Header from "./DashboardHeader"

import Bar from "../../../components/ui/graphs/Bar.jsx"
import Line from "../../../components/ui/graphs/Line.jsx"
import Heatmap from "../../../components/ui/graphs/Heatmap.jsx"

export default function Circulation() {
    
    return (
        <div className={styles.circulation}>
            <Header />
            <div className={styles.container}>
                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Borrows (time range)</p>
                </div>
                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Active Borrowers</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.value}>0</p>
                    <p className={styles.label}>Currently Overdue</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.value}>1st</p>
                    <p className={styles.label}>Semester Timeline</p>
                </div>

                <div className={styles.panel}>
                    <Line
                        header={"Total Checkouts"}
                        subHeader={"By day of week"}
                        data={[]}
                    />
                </div>

                <div className={styles.panel}>
                    <Bar
                        header={"Top 10 most borrowed books"}
                        subHeader={"Ranked by checkouts"}
                        data={[]}
                    />
                </div>
                
                <div className={styles.panel}>
                    <Heatmap
                        header={"Peak borrowing periods"}
                        subHeader={"Checkouts by day and week of the term"}
                        data={[]}
                    />
                </div>
            </div>

        </div>
    )
}