import styles from "../../../styles/library/showBook/showbook.module.css"
import libby from "../../../assets/pages/library/libby.svg"

import BookPanel from "../BookPanel.jsx"
import { useRecommendations } from "./useRecommendations.js";

export default function RecommendedBooks({ bookId, setActiveBook, setShowBook }) {
    const { items, loading, error } = useRecommendations(bookId);

    if (loading || error) return null;

    if (items.length === 0) {
        return (
            <div className={styles.comingSoonContainer}>
                <img src={libby} />
                <p>No similar items yet.</p>
            </div>
        );
    }

    return items.map(item => (
        <BookPanel
            key={item.book.id}
            book={item.book}
            setActiveBook={setActiveBook}
            setShowBook={setShowBook}
        />
    ));
}
