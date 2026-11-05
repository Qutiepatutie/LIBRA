import styles from "../../../../styles/components/dashboards/graphs/graphcontainer.module.css"

import {Chart as Chartjs, PointElement, LineElement, CategoryScale, LinearScale, Tooltip, Legend} from "chart.js"
import { Line } from "react-chartjs-2"

import getNiceScale from "./getNiceScale";

export default function LineGraph({header, subHeader, data, category = "user", label = "month"}) {

    Chartjs.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);

    const labels = {
        month: [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ],
        day: [
            "Mon", "Tue", "Wed", "Thu", "Fri", "Sat",
        ]
    };

    const dataset = Array(labels[label]?.length).fill(0);

    data?.forEach(item => {
        const period = category === "user"
            ? item.month.split("-")[1]
            : category === "circulation"
                ? labels[label].indexOf(item.label)+1
                : labels[label].indexOf(item.day)+1

        const index = Number(period) - 1;

        if (index >= 0 && index < 12) {
            dataset[index] += item.count;
        }
    })

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
                            labels: labels[label],
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
