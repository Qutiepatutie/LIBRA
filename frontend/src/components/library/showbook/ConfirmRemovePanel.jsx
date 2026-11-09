import styles from "../../../styles/library/showBook/confirmremove.module.css"

import CustomButton from "../../ui/CustomButton"

export default function ConfirmRemovePanel({setShowConfirm, handleRemoveBook, loading}){
    return (
        <div className={styles.backdrop}>
            <div className={styles.container}>
                <div className={styles.body}>
                    <p>The book will be archived and can be added again in the Add Books page</p>
                </div>
                <div className={styles.buttons}>
                    <CustomButton
                        value={"Cancel"}
                        action={"clear"}
                        onClick={() => setShowConfirm(false)}
                    />
                    <CustomButton
                        value={"Confirm"}
                        action={"cancel"}
                        disabled={loading}
                        onClick={() => handleRemoveBook()}
                    />
                </div>
            </div>
        </div>
    )
}