import WebcamCapture from "./WebcamCapture.jsx"
import jsQR from "jsqr"
import { useEffect } from "react";

export default function QRScanner({ setData }) {

     const handleScan = (imageSrc) => {
          if (imageSrc) {
               const image = new Image();
               image.src = imageSrc;
               image.onload = () => {
                    const canvas = document.createElement("canvas");
                    canvas.width = image.width;
                    canvas.height = image.height;
                    const ctx = canvas.getContext("2d");
                    if (!ctx) return;
                   
                    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    const code = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: "dontInvert" });

                    if (code) {
                        setData(code.data);
                    }
               }
          }
     }
    return (
        <WebcamCapture onScan={handleScan} />
     )
}