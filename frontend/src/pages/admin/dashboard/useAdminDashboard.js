import { useState, useEffect } from "react";

import { getAdminCirculationAnalytics, getAdminInventoryAnalytics, getAdminBorrowersAnalytics } from "../../../api/analytics";

export function useAdminAnalytics() {
    const [circulationData, setCirculationData] = useState([]);
    const [inventoryData, setInventoryData] = useState([]);
    const [borrowersData, setBorrowersData] = useState([]);

    useEffect(() => {
        async function getAnalytics() {
            const [circulation, inventory, borrowers] = await Promise.all([
                getAdminCirculationAnalytics(),
                getAdminInventoryAnalytics(),
                getAdminBorrowersAnalytics(),
            ]);

            setCirculationData(circulation);
            setInventoryData(inventory);
            setBorrowersData(borrowers);
        }

        getAnalytics();
    }, []);

    return {
        circulationData,
        inventoryData,
        borrowersData,
    }
}