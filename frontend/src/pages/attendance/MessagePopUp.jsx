import styles from "../../styles/attendance/messagepopup.module.css"

export default function MessagePopUp({ id }) {
    
    const formatID = (id) => {
        if (!id) return;
        
        const left = id.slice(0, 4);
        const right = id.slice(-2);
        
        return `${left}*****${right}` 
    }
    
    return (
        <div className={styles.backdrop}>
            <div className={styles.container}>
                <p className={styles.header}>Welcome!</p>
                <p className={styles.body}>Student ID: <span><u>{formatID(id)}</u></span></p>
            </div>
        </div>
    )
}