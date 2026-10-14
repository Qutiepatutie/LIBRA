import styles from "../../styles/library/bookpanel.module.css"

import info from "../../assets/pages/bookpanel/info-icon.svg"

export default function BookPanel({ setActiveBook, setShowBook, status = null, book, hover = true }) {
    return (
        <div
            className={`${styles.bookPanel} ${hover ? "" : styles.noHover}`}
            onClick={() => {
                if (!hover) return;
                setActiveBook(book);
                setShowBook(true);
                }
            }
        >
            <div className={styles.cover}>
                <img src={book?.cover_url} />
                {status && 
                    <div className={styles.detailsPill}>
                        <p>Tap for details</p>
                        <img src={info} className={styles.icon} />
                    </div>
                }
                <div className={styles.info}>
                    <p className={styles.title}>{book?.title}</p>
                    <p className={styles.author}>by {book?.author}</p>
                </div>
            </div>
        </div>
    )
}