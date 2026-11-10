import styles from "../../../styles/components/layout/usermenu.module.css"

import { useState, useRef } from "react"
import { toPng } from "html-to-image"

import logoutIcon from "../../../assets/sidebar/logout.svg"
import avatar from "../../../assets/id/profile-icon.png"
import side from "../../../assets/id/id_side.svg"
import top from "../../../assets/id/id_top.svg"
import olfu from "../../../assets/id/olfu_logo.svg"

import { getStorage } from "../../../pages/auth/auth.util"
import { logout } from "../../../pages/auth/auth.util"
import QRCode from "react-qr-code"

export default function UserMenu({ setShowUserMenu }) {

    const [flipped, setFlipped] = useState(false);

    const [loading, setLoading] = useState(false);

    const fullName = `${getStorage().getItem("user_firstName")} ${getStorage().getItem("user_lastName")}`;
    const idNumber = getStorage().getItem("id_number");
    const program = getStorage().getItem("program");

    const frontRef = useRef(null);
    const backRef = useRef(null);

    const loadImage = (src) => {
        return new Promise((resolve, reject) => {
            const image = new Image();
    
            image.onload = () => resolve(image);
            image.onerror = reject;
    
            image.src = src;
        });
    }
    
    const exportID = async () => {
        try {
            setLoading(true);

            const options = {
                pixelRatio: 3,
                cacheBust: true,
                style: {
                    transform: "none",
                    backfaceVisibility: "visible"
                }
            };
            
            await document.fonts.ready;

            const frontImage = await toPng(frontRef.current, options);
            const backImage = await toPng(backRef.current, options);

            const [front, back] = await Promise.all([
                loadImage(frontImage),
                loadImage(backImage)
            ]);

            // Create combined canvas
            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
    
            const width = front.width;
            const height = front.height;
            
            const gap = 30;
            const padding = 50;
    
            canvas.width = width * 2 + gap + padding * 2;
            canvas.height = height+ padding * 2;
    
            // White background
            ctx.fillStyle = "white";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
    
            // Draw both ID sides
            ctx.drawImage(front, padding, padding);
            ctx.drawImage(back, padding+ width + gap, padding);
    
            // Download combined image
            const link = document.createElement("a");
    
            link.download = `${idNumber}-ID.png`;
            link.href = canvas.toDataURL("image/png");
    
            link.click();
        } catch (err) {
            console.log(err);
        } finally {
            setLoading(false);
        }
    }
    
    
    return (
        <div className={styles.backdrop} onClick={() => setShowUserMenu(false)}>
            <div className={styles.container}>
                <div className={styles.userMenu} onClick={(e) => e.stopPropagation()}>
                    <div className={styles.header}></div>
                    <div
                        className={styles.idContainer}
                        onClick={() => setFlipped(prev => !prev)}
                    >
                        <div className={`${styles.idInnerContainer} ${flipped ? styles.flipped : ""}`}>
                            <div ref={frontRef} className={styles.idFront}>
                                <div className={styles.content}>
                                    <div className={styles.avatarContainer}>
                                        <img className={styles.avatar} src={avatar}/>
                                        <div
                                            className={styles.uploadImage}
                                            onClick={(e) => e.stopPropagation()}
                                        >Upload Image</div>
                                    </div>
                                    <div className={styles.infoContainer}>
                                        <div className={styles.info}>
                                            <p>{fullName}</p>
                                            <span>Name</span>
                                        </div>
                                        
                                        <div className={styles.info}>
                                            <p>{idNumber}</p>
                                            <span>ID Number</span>
                                        </div>
                                        
                                        <div className={styles.info}>
                                            <p>{program}</p>
                                            <span>Program</span>
                                        </div>
                                    </div>
                
                                    <div className={styles.footer}>
                                        <img src={olfu} />
                                        <p>Our Lady of Fatima University Laguna</p>
                                    </div>
                                </div>
            
                                <div className={styles.side}>
                                    <img src={side} />
                                </div>
                            </div>
        
                            
                            <div ref={backRef} className={styles.idBack}>
                                <div className={styles.top}>
                                    <img src={top} />
                                </div>
    
                                <div className={styles.content}>
                                    <div className={styles.qrContainer}>
                                        <div className={styles.qr}>
                                            <QRCode
                                                size={256}
                                                value={idNumber}
                                                style={{height: "100%", width: "100%"}}
                                            />
                                        </div>
                                        <p>This card is for library use only</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <button
                        className={styles.export}
                        onClick={() => { exportID() }}
                        disabled={loading}
                    >
                        <p>Export ID</p>
                    </button>
                </div>
    
                <div className={styles.button}>
                    <button className={styles.logout} onClick={() => logout()}>
                        <img src={logoutIcon}/>
                        <p>Logout</p>
                    </button>
                </div>
            </div>
        </div>
    )
}