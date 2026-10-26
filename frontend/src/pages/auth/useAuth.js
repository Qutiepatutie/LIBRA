import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login as loginAPI, googleLogin as googleLoginAPI, changePass, register as registerAPI } from "../../api/users.js"
import { routes } from "./auth.constants.js";
import { requestGoogleCode } from "./auth.util.js";

export function useAuth() {

    const [isLoading, setIsLoading] = useState(false);
    const [toastMessage, setToastMessage] = useState("");
    const [showToast, setShowToast] = useState(false); 
    
    const [errorMessage, setErrorMessage] = useState("");
    
    const navigate = useNavigate();
    
    function showToastFunc(message) {
        setToastMessage(message);
        
        // Show toast for 3 seconds
        setShowToast(() => {
            const timer = setTimeout(() => {
                setShowToast(false);
                setToastMessage("");
            }, 3000); // 3 seconds
    
            return () => clearTimeout(timer);
        });
    }

    function saveSession(resp, rememberMe) {
        const { role, profile } = resp.user;
        const { access, refresh } = resp;

        const storage = rememberMe ? localStorage : sessionStorage;

        storage.setItem("user_firstName", profile?.first_name);
        storage.setItem("user_lastName", profile?.last_name);
        storage.setItem("id_number", profile?.id_number);
        storage.setItem("program", profile?.program);
        storage.setItem("role", role);
        storage.setItem("access", access);
        storage.setItem("refresh", refresh);

        navigate(routes[role] || "/");
    }

    async function login(loginCredentials, rememberMe) {
        try {
            setErrorMessage("");
            setIsLoading(true);
            const resp = await loginAPI(loginCredentials.email, loginCredentials.pass)

            if (resp.status !== 200) {
                showToastFunc(resp.message);
                return false;
            }

            saveSession(resp, rememberMe);

            return true;
        } catch (error) {
            console.log(error);
            showToastFunc("Login failed. Please try again");
            return false;
            
        } finally {
            setIsLoading(false);
        }
    }

    // Resolves to the pending sign-up ({ email, google_token }) when the Google account has no user yet
    async function googleLogin(rememberMe) {
        let code;

        try {
            setErrorMessage("");
            code = await requestGoogleCode();
        } catch {
            // Popup closed or Google script blocked
            return null;
        }

        try {
            setIsLoading(true);
            const resp = await googleLoginAPI(code);

            if (resp.status === 404 && resp.google_token) {
                return { email: resp.email, google_token: resp.google_token };
            }

            if (resp.status !== 200) {
                showToastFunc(resp.message);
                return null;
            }

            saveSession(resp, rememberMe);
            return null;

        } catch {
            showToastFunc("Google sign-in failed. Please try again");
            return null;

        } finally {
            setIsLoading(false);
        }
    }

    async function forgotPass(forgotPassData) { try {
            setIsLoading(true);
            const resp = await changePass(forgotPassData.email, forgotPassData.newPass);

            if (resp.status !== 200) {
                showToastFunc(resp.message);
                return false;
            }
            
            showToastFunc(resp.message);
            return true;
            
        } catch {
            showToastFunc("Changing the password failed. Please try again");
            return false;
            
        } finally {
            setIsLoading(false);
        }
    }

    async function register(payload) {
        try {
            setIsLoading(true);
            const resp = await registerAPI(payload);
        
            if (resp.status !== 201) {
                showToastFunc(resp.message);
                return false;
            }
    
            showToastFunc(resp.message);
            return true;
            
        } catch {
            showToastFunc("Register failed. Please try again");
            return false;
            
        } finally {
            setIsLoading(false);
        }
    }

    return {
        showToast,
        
        // messages
        toastMessage,
        errorMessage,

        // states
        isLoading,

        // setters
        setErrorMessage,

        // actions
        login,
        googleLogin,
        forgotPass,
        register,
    };
}