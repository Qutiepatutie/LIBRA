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

    const [coverImage, setCoverImage] = useState(null);
    const [coverPreview, setCoverPreview] = useState("");
    
    const coverInputRef = useRef(null);
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

    useEffect(() => {
        return () => {
            if (coverPreview) {
                URL.revokeObjectURL(coverPreview);
            }
        };
    }, [coverPreview]);

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

        setCoverImage(null);
        setCoverPreview("");

        if (coverInputRef.current) {
            coverInputRef.current.value = "";
        }
        
        lastISBNRef.current = "";
    }

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (isSubmitting) return;

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

        if(!bookData.cover_url && !coverImage) {
            setToastMessage("Invalid Book");
            notify();
            return;
        }

        const resp = await addBook(bookData, coverImage);
        notify();

        if (resp.status === 201 || resp.status === 200) {
            handleClear();
        }
        // setBookData(prev => ({
        //     ...prev,
        //     ...Object.fromEntries(
        //         Object.entries(initialFormValues).filter(([key]) => (
        //             key !== "classification"
        //         ))
        //     )
        // }))
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

    const handleCoverChange = (e) => {
        console.log(e.target.files[0]);
        const file = e.target.files[0];

        if (!file) return;

        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp",
        ];

        if (!allowedTypes.includes(file.type)) {
            setToastMessage("Only JPG, PNG, and WEBP images are allowed");
            notify();
            e.target.value = "";
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            setToastMessage("Image must not exceed 5MB");
            notify();
            e.target.value = "";
            return;
        }

        setCoverImage(file);

        const previewURL = URL.createObjectURL(file);
        console.log(previewURL);
        setCoverPreview(previewURL);

        setBookData(prev => ({
            ...prev,
            cover_url: ""
        }));
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

                        onClick={() => coverInputRef.current.click()}
                    >
                        {isAutofilling 
                            ? <p>Loading...</p>
                            : coverPreview || bookData.cover_url
                                ? <img src={coverPreview || bookData.cover_url} />
                                : !autofilled
                                    ? <p>Add Cover</p>
                                    : <p>No Available Cover</p> 
                        }
                        <input
                            ref={coverInputRef}
                            type="file"
                            className={styles.coverInput}
                            onChange={handleCoverChange}
                            hidden
                        />
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