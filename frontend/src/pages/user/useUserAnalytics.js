import { useState, useEffect } from "react";

import { getUserAnalytics } from "../../api/analytics";

export function useUserAnalytics() {
    const [analyticsData, setAnalyticsData] = useState({});
    
    useEffect(() => {
        async function getAnalytics() {
            const resp = await getUserAnalytics();
            setAnalyticsData(resp);
            
            console.log(resp);
        }

        getAnalytics();
    }, []);

    return {
        analyticsData,
    }
}