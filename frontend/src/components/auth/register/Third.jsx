import { TextInput, PasswordInput } from "../../ui/Inputs"

export default function Third({ isEmpty, registerData, isEmailLocked, onChange }) {

    return (
        <>
            <TextInput 
                placeholder="Email"
                value={registerData.email}
                name="email"
                onChange={(e) => onChange("email", e.target.value)}
                isEmpty={isEmpty.email}
                disabled={isEmailLocked}
            />        
            
            <PasswordInput 
                placeholder="Password"
                value={registerData.password}
                name="password"
                onChange={(e) => onChange("password", e.target.value)}
                isEmpty={isEmpty.password}
            />        
            
            <PasswordInput
                placeholder="Confirm Password"
                value={registerData.confirm_password}
                name="confirm_password"
                onChange={(e) => onChange("confirm_password", e.target.value)}
                isEmpty={isEmpty.confirm_password}
            />        
        </>
    )
}