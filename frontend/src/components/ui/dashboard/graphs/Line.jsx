import styles from "../../../../styles/components/dashboards/graphs/graphcontainer.module.css"

import {Chart as Chartjs, PointElement, LineElement, CategoryScale, LinearScale, Tooltip, Legend} from "chart.js"
import { Line } from "react-chartjs-2"

export default function LineGraph({header, subHeader, data}) {

    Chartjs.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <p>{header}</p>
                <p className={styles.subHeader}>{subHeader}</p>
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