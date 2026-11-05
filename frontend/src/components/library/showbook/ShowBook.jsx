import styles from "../../../styles/library/showBook/showbook.module.css"
import close from "../../../assets/close-icon.svg"

import { useState, useEffect } from "react";

import CustomButton from "../../ui/CustomButton.jsx";
import BookInfos from "./BookInfos.jsx";

import { details } from "./showbook.constants.js"
import { useUpdateBook } from "./useUpdateBook.js";

import Toast from "../../ui/Toast.jsx"
import ConfirmBorrowPanel from "../ConfirmBorrowPanel.jsx";

// Statuses that hold an item; the backend refuses a new borrow for any of them.
const OPEN_LOAN_STATUSES = ["Pending", "Active", "Due", "Overdue"];

export default function ShowBook({ currBook, onConfirmEdit, showBook, setShowBook, allBorrowers, setAllBorrowers }){
    const role =
        localStorage.getItem("role") || sessionStorage.getItem("role");

    const notify = () => {
        setShowToast(true);
        setTimeout(() => setShowToast(false), 2000);
    }

    const [showConfirm, setShowConfirm] = useState(false);
    const [bookDetails, setBookDetails] = useState(currBook);

    const [showToast, setShowToast] = useState(false);
    
    const {
        loading,
        toastMessage,
        isEdit,
        setIsEdit,
        setToastMessage,
        borrowBook,
        editBook,
    } = useUpdateBook(setShowConfirm, notify);

    // Match on the item id: theses often have no ISBN, so many items share a blank one.
    const isBorrowed = allBorrowers.find(
        b => OPEN_LOAN_STATUSES.includes(b.status) && b.book.id === currBook.id
    );

    const isAdmin = role === "admin";

    const buttonLabel = isAdmin
        ? (isEdit ? "Submit" : "Edit Book")
        : (isBorrowed ? "Borrowed" : "Borrow Book");

    useEffect(() => {
        const handleEsc = (e) => {
            if(e.key === "Escape" && showBook)
                setShowBook(false);
        }

        window.addEventListener("keydown", handleEsc);
        return () => window.removeEventListener("keydown", handleEsc);
    }, [showBook]);

    const handleChange = (e) => {
        const {value, name} = e.target;

        setBookDetails({ ...bookDetails, [name]: value});
    }

    const handleCancelEdit = () => {
        setBookDetails(currBook);
        setIsEdit(false);
    }

    const handleConfirmEdit = async () => {

        const isUnchanged = Object
            .keys(bookDetails)
            .every(key => bookDetails[key] === currBook[key]);

        if(isUnchanged){
            setIsEdit(false);
            return;
        }

        editBook(bookDetails);
        onConfirmEdit(bookDetails);

        setToastMessage("Successfully Edited Book!");
        notify();

        setIsEdit(false);
    }

    const handleConfirmBorrow = (book) => {
        borrowBook(book);

        setAllBorrowers(prev =>
            prev.map(b =>
                b.book.id === book.id
                    ? {...b, status: "Pending"}
                    : b
            )
        );
    }

    return (
        <>
            <Toast message={toastMessage} show={showToast}/>
            <ConfirmBorrowPanel
                showConfirm={showConfirm}
                setShowConfirm={setShowConfirm}
                currBook={currBook}
                loading={loading}
                handleConfirmBorrow={handleConfirmBorrow}
            />
            <div
                className={styles.backdrop}
                onClick={() => setShowBook(false)}
            >
                <div className={styles.close} onClick={() => setShowBook(false)}>
                    <img src={close} />
                </div>
                
                <div className={styles.coverContainer}>
                    <img
                        className={styles.cover}
                        onClick={(e) => e.stopPropagation()}
                        src={bookDetails.cover_url}
                    />
                </div>
                
                <div
                    className={styles.showBook}
                    onClick={(e) => e.stopPropagation()}
                >

                    <div className={styles.bodyContainer}>
                        <div className={styles.infoContainer}>
                            <BookInfos
                                bookDetails={bookDetails}
                                details={details}
                                handleChange={handleChange}
                                isEdit={isEdit}
                            />
                        </div>

                        <div className={styles.buttonContainer}>
                            <div className={styles.buttons}>
                                {isEdit &&
                                    <CustomButton
                                    value="Cancel"
                                    action="cancel"
                                    onClick={handleCancelEdit}
                                    />
                                }
    
                                <CustomButton
                                    value={buttonLabel}
                                    onClick={() => {
                                        if(isAdmin){
                                            return isEdit
                                                ? handleConfirmEdit()
                                                : setIsEdit(true)
                                            }
    
                                            setShowConfirm(true);
                                        }}
                                    disabled={isBorrowed && role !== "admin"}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </>
    )
}
