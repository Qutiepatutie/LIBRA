import styles from "../../styles/userPages/userdashboard.module.css"

import Table from "../../components/ui/dashboard/Table.jsx"

import LineGraph from "../../components/ui/dashboard/graphs/Line.jsx"
import BarGraph from "../../components/ui/dashboard/graphs/Bar.jsx"

import { useUserAnalytics } from "./useUserAnalytics.js"
import { useBorrowedBooks } from "./borrowedBooks/useBorrowedBooks.js"

export default function UserDashboard() {

    const { analyticsData } = useUserAnalytics(); 
    const { borrowedBooks } = useBorrowedBooks();

    console.log(analyticsData);
    borrowedBooks.map(item => console.log(item.due_date));

    const dueThisWeek = borrowedBooks?.filter(item => {
        const start = new Date(analyticsData?.due_soon_window?.start_date?.split("-").at(-1));
        const end = new Date(analyticsData?.due_soon_window?.end_date?.split("-").at(-1));
        const date = new Date(item?.due_date?.split("-").at(-1));

        return date >= start && date <= end;
    }).length ?? 0;

    return (
        <div className={styles.container}>
            <div className={styles.panel}>
                <p className={styles.label}>Total Borrowed</p>
                <p className={styles.value}>{analyticsData?.history_summary?.total_borrowed ?? 0}</p>
            </div>
            <div className={styles.panel}>
                <p className={styles.label}>Overdue</p>
                <p className={styles.value}>{analyticsData?.history_summary?.overdue ?? 0}</p>
            </div>
        
            <div className={styles.panel}>
                <p className={styles.label}>Due this week</p>
                <p className={styles.value}>{dueThisWeek}</p>
            </div>
        
            <div className={styles.panel}>
                <p className={styles.label}>Fine</p>
                <p className={styles.value}>₱ {analyticsData?.history_summary?.fine.outstanding ?? 0}</p>
            </div>

            <div className={`${styles.panel} ${styles.doughnutGraphContainer}`}>
                <LineGraph
                    header={"My Borrowing Frequency"}
                    subHeader={"By month"}
                    data={analyticsData?.borrowing_frequency}
                />
            </div>
            
            <div className={`${styles.panel} ${styles.barGraphContainer}`}>
                <BarGraph
                    header={"Most Borrowed Subjects"}
                    subHeader={"Based on your history"}
                    data={analyticsData.most_borrowed_subjects}
                />
            </div>
        
            <div className={`${styles.panel} ${styles.books}`}>
                <Table />
            </div>
        </div>
    )
}