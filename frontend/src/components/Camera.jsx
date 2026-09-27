
import { useEffect, useRef, useState } from "react";
import "../styles/Camera.css";

import SearchResults from "./SearchResults.jsx";


function Camera() {
    const videoRef = useRef(null);
    const fileRef = useRef(null);
    const streamRef = useRef(null);

    const [ready, setReady] = useState(false);
    const [cameraError, setCameraError] = useState(null);
    const [photo, setPhoto] = useState(null);

    useEffect(() => {
        let stream = null;

        async function start() {
            try {
                stream = await navigator.mediaDevices.getUserMedia({
                    audio: false,
                    video: {
                        facingMode: { ideal: "environment" },  // задняя камера
                        width: { ideal: 1920 },
                        height: { ideal: 1080 },
                    },
                });
                streamRef.current = stream;
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                    await videoRef.current.play();
                }
                setReady(true);
            } catch {
                setCameraError("Камера недоступна. Загрузите фото из галереи.");
            }
        }

        start();

        return () => stream?.getTracks().forEach((t) => t.stop());
    }, []);

    function takePhoto() {
        const video = videoRef.current;
        if (!video || !video.videoWidth) return;

        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);

        canvas.toBlob((blob) => {
            if (blob) setPhoto(blob);
        }, "image/jpeg", 0.92);
    }

    function onFilePick(e) {
        const file = e.target.files?.[0];
        if (file) setPhoto(file);
        e.target.value = "";
    }

    if (photo) {
        return <SearchResults photo={photo} onRetry={() => setPhoto(null)} />;
    }

    return (
        <div className="camera-screen">
            <video ref={videoRef} className="camera-video" autoPlay muted playsInline />

            <div className="camera-hint">
                Наведите камеру на этикетку бутылки российского производителя
            </div>

            <div className="camera-sheet">
                <button className="round-btn" aria-label="Назад">←</button>
                <button
                    className="shutter-btn"
                    onClick={takePhoto}
                    disabled={!ready}
                    aria-label="Сделать снимок"
                />
                <button
                    className="round-btn"
                    onClick={() => fileRef.current.click()}
                    aria-label="Из галереи"
                >
                    🖼
                </button>
            </div>

            <input ref={fileRef} type="file" accept="image/*" hidden onChange={onFilePick} />

            {cameraError && <div className="camera-error">{cameraError}</div>}
        </div>
    );
}


export default Camera;