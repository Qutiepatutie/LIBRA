import styles from "../../styles/library/library.module.css"

import { useState } from "react"

import { SearchBar } from "../../components/ui/Inputs.jsx"

import CategoryPanel from "../../components/library/CategoryPanel.jsx"
import ExpandedCategory from "../../components/library/ExpandedCategory.jsx"
import ShowBook from "../../components/library/showbook/ShowBook.jsx"
import BookPanel from "../../components/library/BookPanel.jsx"

import { categories } from "./library.constants.js"
import { useLibraryBooks } from "./useLibraryBooks.js"
import { useBorrowers } from "../../hooks/useBorrowers.js"

export default function Library() {

    const { books,
            searchedBooks,
            updateBook,
            searchBooks } = useLibraryBooks();
    
    const { allBorrowers, setAllBorrowers } = useBorrowers();

    const [searchQuery, setSearchQuery] = useState("");
    const [searching, setSearching] = useState(false);

    const [activeCategory, setActiveCategory] = useState("");
    const [showCategory, setShowCategory] = useState(false);    

    const [activeBook, setActiveBook] = useState("");
    const [showBook, setShowBook] = useState(false);

    const handleUpdateBook = (updatedBook) => {
        updateBook(updatedBook, activeBook);
        setActiveBook(updatedBook);
    }

    const handleSearchBooks = (e) => {
        e.preventDefault();

        if(!searchQuery.trim()){
            setSearching(false);
            return;
        }

        searchBooks(searchQuery);
        setSearching(true);    
    }

    let content;

    if(searching){
        content = 
            searchedBooks.length 
            ? searchedBooks.map((book) => (
                    <BookPanel 
                        key={book.ISBN}
                        setActiveBook={setActiveBook}
                        showBook={showBook}
                        setShowBook={setShowBook}
                        book={book}
                    />
                ))
             : <h1 className={styles.noBooks}>No Books Found</h1>
    } else {
        content =
            <CategoryPanel
                categories={categories}
                books={books}
                setActiveCategory={setActiveCategory}
                setShowCategory={setShowCategory}
                showBook={showBook}
                setShowBook={setShowBook}
                setActiveBook={setActiveBook}    
             />
    }

    return (
        <>
            <div className={styles.library}>
                <form className={styles.header} onSubmit={handleSearchBooks}>
                    <SearchBar
                        name="search"
                        value={searchQuery}
                        label="Find all the literatures you want in just one search"
                        placeholder="Search title, author, ISBN"
                        onChange={(e) => {
                            if(!e.target.value){
                                setSearching(false);
                            }
                            setSearchQuery(e.target.value)
                        }} 
                    />
                </form>
                <div className={`${styles.content} ${searching 
                        ? !searchedBooks.length ? "" : styles.searching 
                        : ""
                    }`
                }>
                    {content}
                </div>

                <ExpandedCategory
                    showCategory={showCategory}
                    setShowCategory={setShowCategory}
                    categories={categories}
                    activeCategory={activeCategory}
                    books={books[activeCategory]}
                    setActiveBook={setActiveBook}    
                    showBook={showBook}
                    setShowBook={setShowBook}
                />
                
                {showBook && (
                    <ShowBook 
                        setShowBook={setShowBook}
                        currBook={activeBook}
                        onConfirmEdit={handleUpdateBook}
                        allBorrowers={allBorrowers}
                        setAllBorrowers={setAllBorrowers}
                    />
                )}
            </div>
        </>
    )
}