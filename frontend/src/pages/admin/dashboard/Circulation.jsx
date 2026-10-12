import styles from "../../../styles/adminPages/dashboard/circulation.module.css" 

import Header from "./DashboardHeader"

import Bar from "./graphs/Bar.jsx"
import Line from "./graphs/Line.jsx"
import Heatmap from "./graphs/Heatmap.jsx"

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
                        data={[]}
                    />
                </div>

                <div className={styles.panel}>
                    <Bar
                        data={[]}
                    />
                </div>
                
                <div className={styles.panel}>
                    <Heatmap
                        data={[]}
                    />
                </div>
            </div>

        </div>
    )
}