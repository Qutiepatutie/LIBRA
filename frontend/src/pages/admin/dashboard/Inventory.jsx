import styles from "../../../styles/adminPages/dashboard/inventory.module.css"

import Table from "../../../components/ui/dashboard/Table"

import { useAdminAnalytics } from "./useAdminDashboard.js"

export default function Inventory() {

    const { inventoryData } = useAdminAnalytics();
    const { statistics, overdue_items } = inventoryData;
    
    return (
        <div className={styles.container}>
            <div className={styles.panel}>
                <p className={styles.label}>Available</p>
                <p className={styles.value}>{statistics?.available?.value || 0}</p>
                <p className={styles.label}>{statistics?.available?.percentage || 0}% of collection</p>
            </div>
            <div className={styles.panel}>
                <p className={styles.label}>Borrowed</p>
                <p className={styles.value}>{statistics?.borrowed?.value || 0}</p>
                <p className={styles.label}>{statistics?.borrowed?.percentage || 0}% of collection</p>
            </div>

            <div className={styles.panel}>
                <p className={styles.label}>Overdue</p>
                <p className={styles.value}>{statistics?.overdue?.value || 0}</p>
                <p className={styles.label}>{statistics?.overdue?.percentage || 0}% of collection</p>
            </div>

            <div className={styles.panel}>
                <p className={styles.label}>Lost/Damaged</p>
                <p className={styles.value}>{statistics?.lost_damaged?.value || 0}</p>
                <p className={styles.label}>{statistics?.lost_damaged?.percentage || 0}% of collection</p>
            </div>
            
            <div className={styles.panel}>
                <Table
                    data={overdue_items}
                />
            </div>
        </div>
    )
}