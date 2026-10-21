import styles from "../../../styles/adminPages/history/books.module.css"

import { useState } from "react";
import { useLocation } from "react-router-dom";

import { SearchBar } from "../../../components/ui/Inputs.jsx"
import { useBorrowers } from "../../../hooks/useBorrowers.js";

import Status from "../../../components/ui/Status.jsx"
import CustomButton from "../../../components/ui/CustomButton.jsx"

export default function History() {
    const { allBorrowers, searchBorrowers } = useBorrowers();
    const [query, setQuery] = useState("");

    const { pathname } = useLocation();
    const page = pathname.split("/").at(-1);
    
    const borrowerList = query
    ? searchBorrowers(allBorrowers, query)
    : allBorrowers;

    const reservationList = [];

    const tableData = {
        books: {
            headers: [
                "ID Number",
                "Name",
                "Program",
                "Call Number",
                "Borrow Date",
                "Due Date",
                "Return Date",
                "Status",
            ],
            list: borrowerList,
        },
        rooms: {
            headers: [
                "ID Number",
                "Name",
                "Program",
                "LRC",
                "Room",
                "Date",
                "Time",
                "Status",
            ],
            list: reservationList,
        }
    }
    
    const isRecordFound = tableData[page].list.length > 0;

    const handleExport = () => {
        const apiUrl = import.meta.env.VITE_API_URL;

        const endPoints = {
            books: "exportBorrowedBooksCSV",
            rooms: "exportRoomReservationsCSV"
        }
        const endPoint = endPoints[page];
        
        window.open(`${apiUrl}/${endPoint}`, "_blank");
    }

    return (
        <div className={styles.borrowers}>
            <div className={styles.header}>
                <SearchBar 
                    placeholder="Search by name or ID number"
                    name="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />
            </div>
            <div className={styles.tableContainerWrapper}>
                <div 
                    className={styles.tableContainer}
                    style={{display:(isRecordFound ? "" : "flex")}}    
                >
                    {!isRecordFound
                    ?   <h1 className={styles.noRecord}>No Records Found</h1>
                    :   <table>
                            <colgroup>
                                <col />
                                <col />
                                <col />
                                <col />
                                <col />
                                <col />
                                <col />
                                <col />
                                <col />
                            </colgroup>
                            <thead>
                                <tr>
                                    <th></th>
                                    {Object.entries(tableData[page].headers).map(([_,header]) => (
                                        <th key={header}>{header}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {page === "books" &&
                                    borrowerList.map((b, index) => (
                                        <tr key={index}>
                                            <td>{index + 1}</td>
                                            <td>{b.user.id_number}</td>
                                            <td>{`${b.user.first_name} ${b.user.last_name}`}</td>
                                            <td>{b.user.program}</td>
                                            <td>{b.book.call_number}</td>
                                            <td>{b.borrow_date ? b.borrow_date.slice(0, 10) : "--"}</td>
                                            <td>{b.due_date ? b.due_date.slice(0, 10) : "--"}</td>
                                            <td>{b.return_date ? b.return_date.slice(0, 10) : "--"}</td>
                                            <td className={styles.status}><Status status={b.status} /></td>
                                        </tr>
                                    ))
                                }
                            </tbody>
                        </table> 
                    }
                </div>
            </div>
            <div className={styles.buttonContainer}>
                <CustomButton 
                    onClick={handleExport}
                    value="Export Data"
                />
            </div>
        </div>
    )
}