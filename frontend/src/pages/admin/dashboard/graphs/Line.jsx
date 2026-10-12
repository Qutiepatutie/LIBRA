import styles from "../../../../styles/userPages/dashboard/graphcontainer.module.css"

import {Chart as Chartjs, PointElement, LineElement, CategoryScale, LinearScale, Tooltip, Legend} from "chart.js"
import { Line } from "react-chartjs-2"

export default function LineGraph({ data }) {

    Chartjs.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <p>Total Checkouts</p>
                <p className={styles.subHeader}>By day of week</p>
            </div>
            <div className={styles.graphContainer}>
                <div className={styles.graph}>
                    <Line
                        data={{
                            labels: data?.map(data => data.label), 
                            datasets: [
                                {
                                    data: data?.map(data => data.data),
                                    fill: false,
                                    pointBackgroundColor: "#5D6D4F",
                                    borderColor: "#5D6D4F",
                                    showLine: true,
                                }
                            ],
                        }}
                        options={{
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    display: false,
                                },
                                tooltip: {
                                    enabled: false,
                                }
                            },
                        }}
                    />
                </div>
            </div>
        </div>
    )
}