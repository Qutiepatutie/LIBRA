import styles from "../../../../styles/components/dashboards/graphs/graphcontainer.module.css"

import {Chart as Chartjs, CategoryScale, LinearScale, BarElement, Tooltip, Legend} from "chart.js"
import { Bar } from "react-chartjs-2"

import getNiceScale from "./getNiceScale";

export default function BarGraph({header, subHeader, data}) {
    
    Chartjs.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

    const labels = {
        user: [
            "001 General Information",
            "100 Philosophy & Psychology",
            "200 Religion",
            "300 Social Sciences",
            "400 Language",
            "500 Science",
            "600 Technology",
            "700 Arts & Recreation",
            "800 Literature",
            "900 History & Geography",
        ]
    }

    const dataset = labels["user"].map(label => {
        const entry = data?.subjects?.find(
            item => item.code === label.split(" ")[0]
        );

        return entry ? entry.count : 0;
    })
    
    const maxCount = Math.max(...(data?.subjects?.map(item => item.count) ?? [0]))
    const { interval, xAxisMax } = getNiceScale(maxCount);
    
    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <p>{header}</p>
                <p className={styles.subHeader}>{subHeader}</p>
            </div>
            <div className={styles.graphContainer}>
                <div className={`${styles.graph} ${styles.bar}`}>
                    <Bar
                        data={{
                            labels: labels["user"],
                            datasets: [
                                {
                                    data: dataset,
                                    backgroundColor: [
                                        "#5D6D4F",
                                    ],
                                },
                            ],
                        }}
                        options={{
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    display: false,
                                },
                                tooltip: {
                                    enabled: true,
                                    displayColors: false,
                                    callbacks: {
                                        label: (context) => `Books Borrowed: ${context.parsed.x}`
                                    }
                                }
                            },
                            indexAxis: 'y',
                            scales: {
                                y: {
                                    ticks: {
                                        crossAlign: "far",
                                    },
                                },
                                x: {
                                    min: 0,
                                    max: xAxisMax,
                                    ticks: {
                                        stepSize: interval
                                    }
                                }
                            }
                        }}
                    />
                </div>
            </div>
        </div>
    )
}