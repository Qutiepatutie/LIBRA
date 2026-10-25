import styles from "../../styles/authPage/login.module.css"

import google from "../../assets/auth/login/google.svg";

import CustomButton from "../ui/CustomButton";
import { TextInput, PasswordInput, RememberMeBox } from "../../components/ui/Inputs"
import ErrorMessage from "../ui/ErrorMessage.jsx";
import useForm from "../../hooks/useForm";

export default function Login({ isEmpty, setIsEmpty, credentials, setCredentials, rememberMe, setRememberMe, handleSwitch, handleGoogleLogin, setErrorMessage, errorMessage, isLoading }) {

    const { handleChange } = useForm({
        setData: setCredentials,
        setIsEmpty,
        setErrorMessage
    });

    return (
        <div className={styles.login}>
            <div className={styles.inputs}>
                <TextInput
                    value={credentials.email}
                    placeholder="Email"
                    name="email"
                    onChange={(e) => handleChange("email", e.target.value)}
                    isEmpty={isEmpty.email}
                />
                
                <PasswordInput
                    placeholder="Password"
                    value={credentials.pass}
                    name="password"
                    onChange={(e) => handleChange("pass", e.target.value)}
                    isEmpty={isEmpty.pass}
                />

            </div>
            
            <ErrorMessage message={errorMessage} />

            <div className={styles.buttons}>
                <div className={styles.actionButtons}>
                    <RememberMeBox isChecked={rememberMe} setIsChecked={setRememberMe}/>  
                    <p
                        className={styles.forgotPass}
                        onClick={() => handleSwitch("forgotPass")}
                    >
                        <u>Forgot Password?</u>
                    </p>
                </div>
                <div className={styles.loginButton}>
                    <CustomButton
                        value={isLoading ? "Logging in..." : "Login"}
                        type="submit"
                        action={isLoading ? "loading" : ""}
                    />
                </div>
            </div>

            <div className={styles.divider}>or</div>
                
            <div className={styles.googleLoginContainer}>
                <div className={styles.googleLogin} onClick={handleGoogleLogin}>
                    <img src={google}/>
                    <p>Login with Google</p>
                </div>
            </div>
            
        </div>
    )
}