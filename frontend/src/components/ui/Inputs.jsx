import styles from "../../styles/components/inputs.module.css"

import { useState } from "react"

import openBook from "../../assets/auth/login/open-book-icon.svg"
import closedBook from "../../assets/auth/login/closed-book-icon.svg"
import searchIcon from "../../assets/search-icon.svg"

export function TextInput({ label = "", value = "", name = "", placeholder = "", onChange, onBlur, disabled, isEmpty = false }) {
    return (
        <div className={styles.formInput} >
            {label && <label htmlFor={name}>{label}</label>}
            <input
                type="text"
                name={name}
                value={value}
                placeholder={placeholder}
                onChange={onChange}
                onBlur={onBlur}
                className={isEmpty ? styles.empty : ""}
                disabled={disabled}
            />
        </div>
    )
}

export function DescriptionInput({ label="", value="", name="", rows="", onChange, disabled, isEmpty=false, width, style}) {
    return (
        <div className={styles.descriptionInput} style={{width: width}}>
            {label && <label htmlFor={name}>{label}</label>}
            <textarea
                name={name}
                rows={rows}
                value={value}
                onChange={onChange}
                className={isEmpty ? styles.empty : ""}
                style={style}
                disabled={disabled}
            />
        </div>
    )
}

export function Selector({ placeholder="",value="", options, name="", label="", onChange, disabled, isEmpty=false, height}) {
    return (
        <div className={styles.selector}>
            {label && <label htmlFor={name}>{label}</label>}
            <select
                style={{height: height}}
                name={name}
                onChange={onChange}
                value={value}
                className={isEmpty ? styles.empty : ""}
                disabled={disabled}
            >
                <option hidden>{placeholder}</option>
                {options?.map((option, index) => {
                    const isObject = typeof option === "object";

                    const optionCode = isObject ? option.code : option;
                    const optionLabel = isObject
                        ? `${option.code} - ${option.label}`
                        : option;

                    return (
                        <option key={index} value={optionCode}>{optionLabel}</option>
                    )
                })}
            </select>
        </div>
    )
}

export function PasswordInput({ placeholder="", value="", name="", onChange, isEmpty=false }) {
    const [showPass, setShowPass] = useState(false);

    return (
        <div className={styles.formInputPass}>
            <div className={`${styles.passContainer} ${isEmpty ? styles.empty : ""}`}>
                <input
                    type={showPass ? "text" : "password"}
                    name={name}
                    value={value}
                    placeholder={placeholder}
                    onChange={onChange}
                />

                <img
                    src={showPass ? openBook : closedBook}
                    onClick={() => setShowPass(!showPass)}
                />
            </div>
        </div>
    )
}

export function SearchBar({ value="", name="", placeholder="", label="", onChange, onClick }) {
    return (
        <div className={styles.searchBar} >
            {label && ( <label>{label}</label> )}
            <div className={styles.searchContainer}>
                <img
                    src={searchIcon}
                    onClick={onClick}
                />
                <input
                    type="text"
                    name={name}
                    value={value}
                    placeholder={placeholder}
                    onChange={onChange}
                />
            </div>
        </div>
    )
}

export function RememberMeBox({ isChecked, setIsChecked }) {
    return (
        <label className={styles.rememberMe}>
            <input
                type="checkbox"
                checked={isChecked}
                onChange={() => setIsChecked(!isChecked)}
                name="rememberMe"/>
            Remember Me
        </label>
    );
}
