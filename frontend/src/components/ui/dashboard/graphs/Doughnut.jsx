import styles from "../../../../styles/components/dashboards/graphs/graphcontainer.module.css"

import {Chart as Chartjs, DoughnutController, ArcElement, Tooltip, Legend} from "chart.js"
import { Doughnut } from "react-chartjs-2"

export default function DoughnutGraph({header, subHeader, data}) {
    
    Chartjs.register(DoughnutController, ArcElement, Tooltip, Legend);

    const { active_borrowers, inactive_borrowers } = data ?? {};
    
    // TEMPORARY DATA TO DISPLAY THE GRAPH
    const dataset = [{label:"Active", data: active_borrowers?.value ?? 0}, {label:"Inactive", data: inactive_borrowers?.value?? 0}]
    
    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <p>{header}</p>
                <p className={styles.subHeader}>{subHeader}</p>
            </div>
            <div className={styles.graphContainer}>
                <div className={`${styles.graph} ${styles.doughnut}`}>
                    <Doughnut
                        data={{
                            labels: dataset?.map(data => data.label),
                            datasets: [
                                {
                                    label: dataset?.map(item => item.label),
                                    data: dataset?.map(item => item.data),
                                    backgroundColor: [
                                        "#5D6D4F", //Active
                                        "gray" //Inactive
                                    ],
                                },
                            ],
                        }}
                        options={{
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    display: true,
                                    position: "right",
                                },
                                tooltip: {
                                    enabled: true,
                                    displayColors: false,
                                    callbacks: {
                                        label: (context) => `${context.parsed} Users`
                                    }
                                }
                            },
                        }}
                    />
                </div>
            </div>
        </div>
    )
}