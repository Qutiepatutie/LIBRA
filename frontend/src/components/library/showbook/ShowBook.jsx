import styles from "../../../styles/library/showBook/showbook.module.css"
import close from "../../../assets/close-icon.svg"
import trash from "../../../assets/pages/library/trash.svg"
import libby from "../../../assets/pages/library/libby.svg"

import { useState, useEffect } from "react";

import CustomButton from "../../ui/CustomButton.jsx";
import { Selector } from "../../ui/Inputs.jsx";
import BookInfos from "./BookInfos.jsx";

import { CONDITIONS, details } from "./showbook.constants.js"
import { useUpdateBook } from "./useUpdateBook.js";
import { getStorage } from "../../../pages/auth/auth.util.js";

import Toast from "../../ui/Toast.jsx"
import ConfirmBorrowPanel from "../ConfirmBorrowPanel.jsx";
import ConfirmRemovePanel from "./ConfirmRemovePanel.jsx";
import BookPanel from "../BookPanel.jsx"

// Statuses that hold an item; the backend refuses a new borrow for any of them.
const OPEN_LOAN_STATUSES = ["Pending", "Active", "Due", "Overdue"];

export default function ShowBook({ currBook, onConfirmEdit, showBook, setShowBook, allBorrowers, setAllBorrowers, refreshBooks }){
    const role = getStorage().getItem("role");

    const notify = () => {
        setShowToast(true);
        setTimeout(() => setShowToast(false), 2000);
    }

    const [showConfirmBorrow, setShowConfirmBorrow] = useState(false);
    const [showConfirmRemove, setShowConfirmRemove] = useState(false);
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
        removeBook,
        addCopy,
        editCopy,
        removeCopy,
    } = useUpdateBook(setShowConfirmBorrow, setShowConfirmRemove, notify);

    // The user already holds a request or loan on some copy of this title.
    const alreadyRequested = allBorrowers.some(
        b => OPEN_LOAN_STATUSES.includes(b.status)
            && b.book.id === currBook.id
            && b.user?.id_number === getStorage().getItem("id_number")
    );

    const noCopies = currBook.available_copies === 0;
    const isBorrowed = alreadyRequested || noCopies;

    const isAdmin = role === "admin";

    const buttonLabel = isAdmin
        ? (isEdit ? "Submit" : "Edit Book")
        : (alreadyRequested ? "Borrowed" : noCopies ? "Unavailable" : "Borrow Book");

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
            .filter(key => !["copies", "total_copies", "available_copies"].includes(key))
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

    const handleConfirmBorrow = async (book) => {
        const resp = await borrowBook(book);

        if(resp?.status !== 200) return;

        setAllBorrowers(prev => [
            ...prev,
            {
                id: resp.loan_id,
                status: "Pending",
                book,
                copy: resp.copy,
                user: { id_number: getStorage().getItem("id_number") },
            }
        ]);
        refreshBooks();
    }

    const handleEditCopy = async (copy, changes) => {
        const resp = await editCopy({ copy_id: copy.id, ...changes });
        if(resp.status === 200) refreshBooks();
    }

    const handleAddCopy = async () => {
        const resp = await addCopy({ book_id: currBook.id });
        if(resp.status === 201) refreshBooks();
    }

    const handleRemoveCopy = async (copy) => {
        const resp = await removeCopy({ copy_id: copy.id });
        if(resp.status === 200) refreshBooks();
    }

    const handleRemoveBook = () => {
        removeBook(currBook.id);

        setShowConfirmRemove(false);
        setShowBook(false);
    }

    return (
        <>
            <Toast message={toastMessage} show={showToast}/>
            <ConfirmBorrowPanel
                showConfirm={showConfirmBorrow}
                setShowConfirm={setShowConfirmBorrow}
                currBook={currBook}
                loading={loading}
                handleConfirmBorrow={handleConfirmBorrow}
            />
            {showConfirmRemove && (
                <ConfirmRemovePanel
                    setShowConfirm={setShowConfirmRemove}
                    loading={loading}
                    handleRemoveBook={handleRemoveBook}
                />
            )}
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


                        <div className={`${styles.buttonContainer} ${role !== "admin" ? styles.column : ""}`}>
                            {role !== "admin" && (
                                <p className={styles.copy}>{currBook.available_copies} of {currBook.total_copies} Copies Available</p>
                            )}
                            
                            {role === "admin" && (
                                <div className={styles.deleteButton}>
                                    <CustomButton 
                                        value={<img className={styles.trash} src={trash} />}
                                        action="delete"
                                        onClick={() => {setShowConfirmRemove(true)}}
                                    />
                                </div>
                            )}
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
    
                                            setShowConfirmBorrow(true);
                                        }}
                                    disabled={isBorrowed && !isAdmin}
                                />
                            </div>
                        </div>
                        
                        {isAdmin && (
                            <div className={styles.copiesContainer}>
                                {currBook.copies?.map(copy => (
                                    <div key={copy.id} className={styles.copy}>
                                        <span className={styles.copyCode}>
                                            c.{copy.copy_number}
                                            {copy.accession_number && ` (${copy.accession_number})`}
                                        </span>
                                        
                                        <div className={styles.copyCondition}>
                                            <Selector
                                                value={copy.condition}
                                                disabled={loading}
                                                onChange={(e) => handleEditCopy(copy, { condition: e.target.value })}
                                                options={CONDITIONS}
                                            />
                                        </div>
                                        
                                        <div className={styles.removeCopy}>
                                            <CustomButton
                                                value={<img className={styles.trash} src={trash} />}
                                                action="delete"
                                                disabled={loading}
                                                onClick={() => handleRemoveCopy(copy)}
                                            />
                                        </div>
                                    </div>
                                ))}
                                <div className={styles.addCopy}>
                                    <CustomButton
                                        value={"Add Copy"}
                                        disabled={loading}
                                        onClick={handleAddCopy}
                                    />
                                </div>
                            </div>
                        )}
                        
                        {role !== "admin" && (
                            <div className={styles.recommendationContainer}>
                                {/* <p className={styles.header}>Recommended Books</p>*/}
                                <div className={styles.recommendations}>
                                    {/* {Array.from({ length: 10 }).map((book, index) => (
                                        <BookPanel
                                            key={index}
                                            book={book}
                                        />
                                    ))}*/}
                                    
                                    {/* TEMP*/}
                                    <div className={styles.comingSoonContainer}>
                                        <img src={libby} />
                                        <p>Book recommendations will be coming soon!</p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </>
    )
}
