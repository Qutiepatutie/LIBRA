import { useState, useEffect } from "react";

import { getAdminCirculationAnalytics, getAdminInventoryAnalytics, getAdminBorrowersAnalytics } from "../../../api/analytics";

export function useAdminAnalytics() {
    const initialParams = {
        range: "day",
        item_type: "",
        program: "all",
        academic_year: "",
        semester: "",
        education_level: "",
    }
    
    const [params, setParams] = useState(initialParams);
    const [appliedParams, setAppliedParams] = useState(initialParams);
    
    const [circulationData, setCirculationData] = useState([]);
    const [inventoryData, setInventoryData] = useState([]);
    const [borrowersData, setBorrowersData] = useState([]);

    const [loading, setLoading] = useState(false);

    useEffect(() => {
        async function getAnalytics() {
            setLoading(true);

            const [circulation, inventory, borrowers] = await Promise.all([
                getAdminCirculationAnalytics(),
                getAdminInventoryAnalytics(),
                getAdminBorrowersAnalytics(),
            ]);

            setCirculationData(circulation);
            setInventoryData(inventory);
            setBorrowersData(borrowers);

            setLoading(false);
        }

        getAnalytics();
    }, []);

    async function getCirculationData(params) {
        setLoading(true);
        const resp = await getAdminCirculationAnalytics(params);

        setCirculationData(resp);
        setLoading(false);
    }
    
    async function getBorrowersData(params) {
        setLoading(true);
        const resp = await getAdminBorrowersAnalytics(params);

        setBorrowersData(resp);
        setLoading(false);
    }

    return {
        initialParams,
        params,
        setParams,
        appliedParams,
        setAppliedParams,
        getCirculationData,
        getBorrowersData,
        circulationData,
        inventoryData,
        borrowersData,
        loading,
    }
}
