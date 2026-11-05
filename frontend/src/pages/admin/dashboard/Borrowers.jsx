import styles from "../../../styles/adminPages/dashboard/borrowers.module.css"

import Header from "./DashboardHeader"

import LineGraph from "../../../components/ui/dashboard/graphs/Line.jsx"
import BarGraph from "../../../components/ui/dashboard/graphs/Bar.jsx"
import DoughnutGraph from "../../../components/ui/dashboard/graphs/Doughnut.jsx"

import { useAdminAnalytics } from "./useAdminDashboard.js"

export default function Borrowers() {

    const { borrowersData } = useAdminAnalytics();

    const {
        statistics,
        borrowing_frequency_by_program: borrowingFrequency,
        checkouts_by_day_of_week: totalCheckouts,
    } = borrowersData ?? {};
    
    const {
        avg_loan_duration_days: loanDuration,
        active_borrowers,
        inactive_borrowers,
        avg_checkouts_per_borrower: avgCheckouts,
    } = statistics ?? {};

    const totalRegistered = () => {
        return (active_borrowers?.value + inactive_borrowers?.value) || 0;
    }
    
    const calculateLoanDuration = () => {
        const { change } = loanDuration ?? {};

        if (!change) return "-";
        
        const sign = change > 0 ? '+' : ''; 
        return `${sign}${change} days vs previous`
    }

    const calculateAvgCheckouts = () => {
        const { change } = avgCheckouts ?? {};

        if (!change) return "-";
        
        const sign = change > 0 ? '+' : ''; 
        return `${sign}${change} vs previous`
    }
    
    return (
        <div className={styles.borrowers}>
            <Header/>
            <div className={styles.container}>
                <div className={styles.panel}>
                    <p className={styles.label}>Total Registered Students</p>
                    <p className={styles.value}>{totalRegistered()}</p>
                    <p className={styles.label}>Across all programs</p>
                </div>
                <div className={styles.panel}>
                    <p className={styles.label}>Avg. Loan Duration</p>
                    <p className={styles.value}>{loanDuration?.value ?? 0} Days</p>
                    <p className={styles.label}>{calculateLoanDuration()}</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.label}>Active Borrowers</p>
                    <p className={styles.value}>{active_borrowers?.value ?? 0}</p>
                    <p className={styles.label}>{active_borrowers?.percentage ?? 0}% of registered</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.label}>Inactive Borrowers</p>
                    <p className={styles.value}>{inactive_borrowers?.value ?? 0}</p>
                    <p className={styles.label}>0 checkouts this semester</p>
                </div>

                <div className={styles.panel}>
                    <p className={styles.label}>Avg. Checkouts per borrower</p>
                    <p className={styles.value}>{avgCheckouts?.value ?? 0}</p>
                    <p className={styles.label}>{calculateAvgCheckouts()}</p>
                </div>
                
                <div className={styles.panel}>
                    <BarGraph
                        header={"Borrowing frequency by programs"}
                        data={borrowingFrequency}
                        category={"borrowers"}
                    />
                </div>

                <div className={styles.panel}>
                    <DoughnutGraph
                        header={"Active vs Inactive users"}
                        subHeader={"Inactive means no checkouts in the selected semester"}
                        data={{active_borrowers, inactive_borrowers}}
                    />
                </div>
                
                <div className={styles.panel}>
                    <LineGraph
                        header={"Total checkouts"}
                        subHeader={"By day of week"}
                        data={totalCheckouts}
                        category={"borrowers"}
                        label={"day"}
                    />
                </div>
                
            </div>
        </div>
    )
}