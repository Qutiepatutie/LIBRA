import { useCallback } from "react";
import { useRef, useEffect } from "react";
import Webcam from "react-webcam"

export default function WebcamCapture({ onScan }) {
     const webcamRef = useRef(null);

     const capture = () => {
        const imageSrc = webcamRef.current.getScreenshot();
        onScan(imageSrc);
     }
          
    useEffect(() => {
        const timer = setInterval(() => {
            capture();
        }, 150);
        return () => clearInterval(timer);
    });
     
     return (
        <Webcam
            audio={false}
            ref={webcamRef}
            screenshotFormat="image/jpeg"
            onClick={capture}
        />
     )
}
