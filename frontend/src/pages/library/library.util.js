export function updateBook(prevBooks, oldBook, updatedBook) {
    const oldCategory = oldBook.call_number.substring(0,3).trim();
    const newCategory = updatedBook.call_number.substring(0,3).trim();
    
    const next = { ...prevBooks };

    next[oldCategory] = next[oldCategory].filter(
        book => book.ISBN !== updatedBook.ISBN
    );

    next[newCategory] = [
        ...(next[newCategory] || []),
        updatedBook
    ];

    return next;
};
