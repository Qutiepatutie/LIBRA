import styles from "../../../styles/components/graphs/graphcontainer.module.css"

import {Chart as Chartjs, DoughnutController, ArcElement, Tooltip, Legend} from "chart.js"
import { Doughnut } from "react-chartjs-2"

export default function DoughnutGraph({header, subHeader, data}) {
    
    Chartjs.register(DoughnutController, ArcElement, Tooltip, Legend);

    // TEMPORARY DATA TO DISPLAY THE GRAPH
    data = [{label:"Active", data: 0}, {label:"Inactive", data: 1}]
    
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
                            labels: data?.map(data => data.label),
                            datasets: [
                                {
                                    label: data?.map(item => item.label),
                                    data: data?.map(item => item.data),
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