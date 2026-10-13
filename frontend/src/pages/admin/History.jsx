import styles from "../../styles/adminPages/history.module.css"

import { useState } from "react";

import { SearchBar } from "../../components/ui/Inputs.jsx"
import { useBorrowers } from "../../hooks/useBorrowers.js";

import Status from "../../components/ui/Status.jsx"
import CustomButton from "../../components/ui/CustomButton.jsx"

export default function History() {

    const { allBorrowers, searchBorrowers } = useBorrowers();

    const [query, setQuery] = useState("");

    const borrowerList = query
    ? searchBorrowers(allBorrowers, query)
    : allBorrowers;
    
    const isRecordFound = borrowerList.length > 0;

    const handleExport = () => {
        const apiUrl = import.meta.env.VITE_API_URL;
        window.open(`${apiUrl}/exportBorrowedBooksCSV/`, "_blank");
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
                            </colgroup>
                            <thead>
                                <tr>
                                    <th></th>
                                    <th>Name</th>
                                    <th>ID Number</th>
                                    <th>Email</th>
                                    <th>Program</th>
                                    <th>Borrow Date</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {borrowerList.map((b, key) => {
                                    console.log(b);
                                    return (
                                        <tr key={key}>
                                            <td>{key+1}</td>
                                            <td>{`${b.user.first_name} ${b.user.last_name}`}</td>
                                            <td>{b.user.id_number}</td>
                                            <td>{b.email}</td>
                                            <td>{b.user.program}</td>
                                            <td>{b.borrow_date ? b.borrow_date.slice(0,10) : "--"}</td>
                                            <td className={styles.status}><Status status={b.status}/></td>
                                        </tr>
                                    )
                                })}
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