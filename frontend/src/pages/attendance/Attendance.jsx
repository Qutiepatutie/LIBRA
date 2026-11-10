import styles from "../../styles/adminPages/attendance.module.css"
import QRScanner from "../../components/qr/QRScanner.jsx"

import { useState, useEffect } from "react"

export default function Attendance() {

     const [data, setData] = useState("");

     useEffect(() => {
          const timer = setInterval(() => {
               setData("");
          }, 3000);
          return () => clearInterval(timer);
     });
     
     return (
          <>
               <div className={styles.container}>
                    <h1>Scan QR Code</h1>
                    <div className={styles.cameraContainer}>
                         <QRScanner setData={setData} className={styles.camera} />
                    </div>
                    <p>{data ? data : "No Result"}</p>
               </div>
          </>
     )
}