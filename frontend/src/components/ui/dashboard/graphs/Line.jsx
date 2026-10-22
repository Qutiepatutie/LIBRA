import styles from "../../../../styles/components/dashboards/graphs/graphcontainer.module.css"

import {Chart as Chartjs, PointElement, LineElement, CategoryScale, LinearScale, Tooltip, Legend} from "chart.js"
import { Line } from "react-chartjs-2"

import getNiceScale from "./getNiceScale";

export default function LineGraph({header, subHeader, data}) {

    Chartjs.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);

    const labels = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];

    const dataset = labels.map((_, index) => {
        const entry = data?.find(
            item => item.month.split("-")[1] === (index + 1).toString().padStart(2, "0")
        );

        return entry ? entry.count : 0;
    });

    const maxCount = Math.max(...data?.map(item => item.count) ?? [0]);

    const { interval, yAxisMax } = getNiceScale(maxCount);
    
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
                            labels: labels,
                            datasets: [
                                {
                                    data: dataset,
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
                                    enabled: true,
                                    displayColors: false,
                                    callbacks: {
                                        label: (context) => `Books Borrowed: ${context.parsed.y}`
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    min: 0,
                                    max: yAxisMax,
                                    ticks: {
                                        stepSize: interval,
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