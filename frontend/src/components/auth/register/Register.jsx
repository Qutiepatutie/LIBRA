import styles from "../../../styles/authPage/register.module.css"

import CustomButton from "../../ui/CustomButton";
import First from "./First.jsx"
import Second from "./Second.jsx"
import Third from "./Third.jsx"
import RegisterProgress from "../../auth/register/RegisterProgress.jsx"
import ErrorMessage from "../../ui/ErrorMessage.jsx";

import useForm from "../../../hooks/useForm.js";

export default function Register({ isEmpty, setIsEmpty, part, setPart, registerData, isEmailLocked, errorMessage, setRegisterData, setErrorMessage, isLoading }) {

    const { handleChange } = useForm({
        setData: setRegisterData,
        setIsEmpty,
        setErrorMessage
    })

    return (
        <div className={styles.register}>

            <div className={styles.progress}>
                <RegisterProgress currentForm={part} />
            </div>

            <div className={styles.inputs}>
                {part === 1 && <First isEmpty={isEmpty} registerData={registerData} onChange={handleChange}/>}
                {part === 2 && <Second isEmpty={isEmpty} registerData={registerData} onChange={handleChange}/>}
                {part === 3 && <Third isEmpty={isEmpty} registerData={registerData} isEmailLocked={isEmailLocked} onChange={handleChange}/>}
                <ErrorMessage message={errorMessage} />
            </div>
            
            <div className={styles.buttons}>
                {part > 1 &&
                    <CustomButton
                        value="Return"
                        onClick={() => {
                            setPart(prev => Math.max(prev - 1, 1))
                            setErrorMessage("");
                        }}
                        type="button"
                        action="return"
                    />
                }
                
                <CustomButton
                    value={part === 3 ? (isLoading ? "Processing..." : "Submit") : "Next"}
                    type="submit"
                />
            </div>
        </div>
    )
}