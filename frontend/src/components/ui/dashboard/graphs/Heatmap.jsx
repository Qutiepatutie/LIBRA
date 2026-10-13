import styles from "../../../../styles/components/dashboards/graphs/heatmap.module.css"

const startDate = new Date("8/17/2026");
const endDate = new Date("12/19/2026");

export default function Heatmap({ header, subHeader, data }) {

    const days = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    const generateWeeks = (start, end) => {
        const weeks = [];
        const startDate = new Date(start);
        const endDate = new Date(end);

        startDate.setDate(
            startDate.getDate() - ((startDate.getDay() + 6) % 7)
        );

        while (startDate <= endDate) {
            const week = [];

            for (let day = 0; day < 6; day++) {
                const date = new Date(startDate);
                week.push(date);
                startDate.setDate(startDate.getDate() + 1);
            }

            startDate.setDate(startDate.getDate() + 1);

            weeks.push(week);
        }

        return weeks;
    }

    const weeks = generateWeeks(startDate, endDate);

    const getCellColor = (count) => {
        if (count === 0) return "#EBEDF0";
        if (count < 5) return "#DCE4D6";
        if (count < 10) return "#A8B99B";
        if (count < 20) return "#788D69";
    
        return "#405536";
    }

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <p>{header}</p>
                <p className={styles.subHeader}>{subHeader}</p>
            </div>
            <div className={styles.heatmapContainer}>
                <div className={styles.heatmap}>
                    <div className={styles.days}>
                        {days.map(day => (
                            <div key={day} className={styles.day}>{day}</div>
                        ))}
                    </div>

                    {/* ROW */}
                    {weeks.map((week, weekIndex) => (
                        <div key={weekIndex} className={styles.week}>
                            <div className={`${styles.cell} ${styles.header}`}>W{weekIndex + 1}</div>
                            
                            {/* COL */}
                            {week.map((date, dateIndex) => {
                                const borrow = data.find(({ date: borrowDate }) => {
                                    return new Date(borrowDate).toDateString() === date.toDateString();
                                });
                                   
                                return (
                                    <div
                                        key={dateIndex}
                                        className={styles.cell}
                                        style={{
                                            backgroundColor: getCellColor(borrow?.count ?? 0)
                                        }}
                                    >
                                        <p className={styles.tooltip}>
                                            {borrow?.count ?? 0} Borrows<br />
                                            <span className={styles.dateText}>{date.toLocaleDateString()}</span>
                                        </p>
                                    </div>  
                                ) 
                            })}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}