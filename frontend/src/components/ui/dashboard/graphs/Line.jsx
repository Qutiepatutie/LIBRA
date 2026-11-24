import styles from "../../../../styles/components/dashboards/graphs/graphcontainer.module.css"

import {Chart as Chartjs, PointElement, LineElement, CategoryScale, LinearScale, Tooltip, Legend} from "chart.js"
import { Line } from "react-chartjs-2"

import getNiceScale from "./getNiceScale";

export default function LineGraph({header, subHeader, data, category = "user", label = "day"}) {

    Chartjs.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);

    const day = [
            "Mon", "Tue", "Wed", "Thu", "Fri", "Sat",
    ]
    
    const labels = {
        year: [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ],
        day: day,
        week: day,
        semester: day,
    };

    const dataset = Array(labels[label]?.length).fill(0);

    data?.forEach(item => {
        let index;
        
        if (category === "user") {
            const month = Number(item.month.split("-")[1]);
            index = month - 1;
        } 
        else if (category === "circulation") {
            if (label === "year") {
                const month = Number(item.label.split("-")[1]);
                index = month - 1;
            } else {
                index = labels[label].indexOf(item.label);
            }
        } 
        else {
            index = labels[label].indexOf(item.day);
        }
        
        if (index >= 0 && index < dataset.length) {
            dataset[index] += Number(item.count);
        }
    });

    const maxCount = Math.max(...dataset, 0);

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
