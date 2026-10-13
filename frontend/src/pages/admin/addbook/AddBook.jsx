import styles from "../../../styles/adminPages/addbook.module.css"

import { useState, useEffect, useRef } from "react"
import Toast from "../../../components/ui/Toast.jsx"

import {
    TextInput, 
    DescriptionInput,
    Selector
} from "../../../components/ui/Inputs.jsx"
import CustomButton from "../../../components/ui/CustomButton.jsx"
import { categories } from "../../library/library.constants.js"
import { 
    initialFormValues,
    initialFormErrors,
    labelToName
} from "./addbook.constants.js"
import { generateCallNumber } from "./addbook.util.js"

import { useAddBook } from "./useAddBook.js"

export default function AddBook() {

    const {
        isAutofilling,
        isSubmitting,
        bookData,
        toastMessage,
        setToastMessage,
        setBookData,
        autofill,
        addBook,
    } = useAddBook();

    const [valueErrors, setValueErrors] = useState(initialFormErrors);
    const [autofilled, setAutofilled] = useState(false);

    const [showToast, setShowToast] = useState(false);

    const lastISBNRef = useRef("");

    const notify = () => {
        setShowToast(true);
        setTimeout(() => setShowToast(false), 2000);
    }

    useEffect(() => {
        if(!autofilled) return;

        setValueErrors(prev => {
            const next = { ...prev };

            for(const key in prev) {
                next[key] = !String(bookData[key] ?? "").trim();
            }
            return next;
        });

    }, [bookData, autofilled])    

    useEffect(() => {
        lastISBNRef.current = "";
    }, [bookData.isbn]);

    useEffect(() => {
        console.log(bookData);
    }, [bookData]);

    const handleChange = (field, value) => {
        setValueErrors(prev => ({ ...prev, [field] : false}));
        setBookData(prev => {
            const updated = {
                ...prev,
                [field]: value
            };

            updated.call_number = generateCallNumber(
                updated.classification.substring(0, 3),
                updated.author,
                updated.year_published
            );

            return updated;
        })
    }

    const handleClear = () => {
        setBookData(initialFormValues);
        setValueErrors(initialFormErrors);
        setAutofilled(false);
        lastISBNRef.current = "";
    }

    const handleSubmit = (e) => {
        e.preventDefault();

        const fields = Object.keys(initialFormErrors);

        const empty = Object.fromEntries(
            Object.keys(initialFormErrors).map(field => [
                field,
                !String(bookData[field] ?? "").trim()
            ])
        );

        setValueErrors(prev => {
            const next = { ...prev };

            Object.keys(next).filter(key => key === "cover_url").forEach(key => next[key] = false);

            fields.forEach(field => {
                next[field] = empty[field];
            });

            return next;
        });

        console.log(empty);

        if(Object.values(empty).some(Boolean)) return;
        console.log("Book Added");

        if(bookData.cover_url === null) {
            setToastMessage("Invalid Book");
            notify();
            return;
        }

        addBook(bookData);
        setBookData(initialFormValues);
        setAutofilled(false);
        if(!isSubmitting) notify();
    }

    const handleAutofill = () => {
        let isbn = bookData.isbn.trim();

        if(isbn.includes("-")) {
            isbn = isbn.replaceAll("-", "");
            setBookData(prev => ({...prev, isbn}));
        }

        if(!isbn || isAutofilling) return;

        if(lastISBNRef.current === isbn) return;

        lastISBNRef.current = isbn;

        if(isNaN(isbn) || (isbn.length !== 10 && isbn.length !== 13)) {
            setValueErrors(prev => ({...prev, "isbn" : true})); 
            setToastMessage("Invalid ISBN");
            notify();
            return;
        }
        autofill(isbn);
        console.log(bookData);
        setAutofilled(true);
    }

    return (
        <>
            <Toast message={toastMessage} show={showToast}/>
            <div className={styles.addbook}>
                <div className={styles.container}>
                    <div className={styles.cover} 
                    style={{borderColor:(bookData.cover_url && !isAutofilling 
                                ? "transparent" 
                                : "")}}
                    >
                        {isAutofilling 
                            ? <p>Loading...</p>
                            : bookData.cover_url
                                ? <img src={bookData.cover_url} />
                                : !autofilled
                                    ? <p>Add Cover</p>
                                    : <p>No Available Cover</p> 
                        }
                    </div>
    
                    <form className={styles.infos} onSubmit={handleSubmit}>
                        <div className={styles.formContainer}>
    
                            {Object.keys(labelToName).map((label) => {
                                const name = labelToName[label];
    
                                const props = {
                                    label: label.replaceAll("_", " "),
                                    name: name,
                                    value: bookData[name],
                                    onChange: (e) => handleChange(name, e.target.value),
                                    isEmpty: valueErrors[name],
                                    disabled: isSubmitting || isAutofilling
                                }
    
                                if(label === "ISBN") {
                                    return (
                                        <TextInput 
                                            key={name}
                                            {...props}
                                            onBlur={handleAutofill}
                                        />
                                    )
                                }
    
                                if(label === "Description") {
                                    return (
                                        <div key={name} className={styles.descriptionWrapper}>
                                            <DescriptionInput {...props} rows="15" />
                                        </div>
                                    );
                                }
    
                                if(label === "Classification") {
                                    return (
                                        <Selector
                                            key={name}
                                            {...props}
                                            options={categories}
                                        />
                                    )
                                }
    
                                return <TextInput key={name} {...props} />;
                            })}
                        </div>
    
                        <div className={styles.buttons}>
                            <CustomButton 
                                value="Clear" 
                                type="button"
                                action="clear"
                                onClick={handleClear}
                            />
    
                            <CustomButton 
                                value={isSubmitting ? "Adding Book" : "Add Book"}
                                action={isSubmitting ? "loading" : ""}
                                type="submit"
                                onClick={handleSubmit}                            
                            />
                        </div>
                    </form>
                </div>
            </div>
        </>
    )
}