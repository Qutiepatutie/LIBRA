import styles from "../../../styles/adminPages/dashboard/circulation.module.css"

import Header from "./DashboardHeader"

import Bar from "../../../components/ui/dashboard/graphs/Bar.jsx"
import Line from "../../../components/ui/dashboard/graphs/Line.jsx"
import Heatmap from "../../../components/ui/dashboard/graphs/Heatmap.jsx"

import { useAdminAnalytics } from "./useAdminDashboard.js"

export default function Circulation() {

    const { circulationData } = useAdminAnalytics();
    
    const {
        statistics,
        top_borrowed,
        peak_periods,
        total_checkouts
    } = circulationData;

    const calculatePct = (data) => {
        const { change_pct } = data ?? {};

        if (!change_pct) return "-";

        const sign = change_pct > 0 ? '+' : '';
        return `${sign}${change_pct / 10}% vs previous`;
    }

    const calculateOverdue = () => {
        const { change } = statistics?.currently_overdue ?? {};

        const sign = change >= 0 ? '+' : '';
        return `${sign}${change ?? 0} since last week`;
    }

    const getSemester = () => {
        const { semester, academic_year } = circulationData?.academic_term?.term ?? {};

        const sem = semester === "1" ? "1st Sem" : semester ? "2nd Sem" : "...";
        const year = academic_year ?? "...";

        return {
            sem,
            year
        }
    }

    return (
        <div className={styles.circulation}>
            <Header />
            <div className={styles.container}>
                <div className={styles.panel}>
                    <p className={styles.label}>Borrows (time range)</p>
                    <p className={styles.value}>0</p>
                </div>
                <div className={styles.panel}>
                    <p className={styles.label}>Active Borrowers</p>
                    <p className={styles.value}>{statistics?.active_borrowers?.value || 0}</p>
                    <p className={styles.label}>{calculatePct(statistics?.active_borrowers)}</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.label}>Currently Overdue</p>
                    <p className={styles.value}>{statistics?.currently_overdue?.value || 0}</p>
                    <p className={styles.label}>{calculateOverdue()}</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.label}>Semester Timeline</p>
                    <p className={styles.value}>{getSemester().sem}</p>
                    <p className={styles.label}>{getSemester().year}</p>
                </div>

                <div className={styles.panel}>
                    <Line
                        header={"Total Checkouts"}
                        subHeader={"By day of week"}
                        data={total_checkouts}
                        category={"circulation"}
                        label={"day"}
                    />
                </div>

                <div className={styles.panel}>
                    <Bar
                        header={"Top 10 most borrowed books"}
                        subHeader={"Ranked by checkouts"}
                        data={top_borrowed}
                        category={"circulation"}
                    />
                </div>

                <div className={styles.panel}>
                    <Heatmap
                        header={"Peak borrowing periods"}
                        subHeader={"Checkouts by day and week of the term"}
                        data={peak_periods}
                    />
                </div>
            </div>

        </div>
    )
}
