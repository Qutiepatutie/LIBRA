import { useState, useEffect } from "react";

import { getRecommendations } from "../../../api/books.js";

export function useRecommendations(bookId) {
    // The result remembers which book it belongs to, so a stale one is never shown.
    const [result, setResult] = useState({ bookId: null, items: [], error: false });

    useEffect(() => {
        let cancelled = false;

        getRecommendations(bookId).then(resp => {
            if (cancelled) return;

            if (resp.status === 200) {
                setResult({ bookId, items: resp.data, error: false });
            } else {
                console.error("Failed to load recommendations", resp);
                setResult({ bookId, items: [], error: true });
            }
        });

        return () => { cancelled = true; };
    }, [bookId]);

    const loading = result.bookId !== bookId;

    return {
        items: loading ? [] : result.items,
        loading,
        error: !loading && result.error,
    };
}
