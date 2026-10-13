import { useState,useEffect } from "react";
import { getBooks } from "../../api/books";
import { categories } from "./library.constants";
import { updateBook as updateBookUtil } from "./library.util";

export function useLibraryBooks() {
    const [books, setBooks] = useState({});
    const [searchedBooks, setSearchedBooks] = useState([]);

    useEffect( () => {
        const fetch = async () => {
            const fetchedBooks = await getBooks();
            console.log(fetchedBooks);

            const bookData = {};

            categories.forEach(({code}) => {
                bookData[code] = [];
            });

            fetchedBooks.data.map((book) => {
                const callNumber = book.call_number.substring(0,3).trim();

                if(bookData[callNumber]){
                    bookData[callNumber].push(book);
                };
            });

            setBooks(bookData);
        };

        fetch();
    }, []);

    function updateBook(updatedBook, activeBook) {
        setBooks(prev => updateBookUtil(prev, activeBook, updatedBook));
    }

    function searchBooks(query) {
        query = query.toLowerCase().trim();

        const allBooks = Object.values(books).flat();

        const filteredBooks = allBooks.filter(book =>
            book.title.toLowerCase().includes(query) ||
            book.author.toLowerCase().includes(query) ||
            book.isbn.trim() === query
        );

        setSearchedBooks(filteredBooks);
    }

    return { books, searchedBooks, updateBook, searchBooks };
}