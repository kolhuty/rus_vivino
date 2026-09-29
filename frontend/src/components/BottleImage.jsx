
import { useState, useEffect } from "react";
import { imageUrl } from "../api.js";


function BottleImage({ slug, src, alt = "" }) {
    const [state, setState] = useState("loading");  // loading | ready | error
    const [loaderInd, setLoaderInd] = useState(0);


    useEffect(() => {
        if (state !== "loading") return;

        const intId = setInterval(() => {
            setLoaderInd((prev) => (prev + 1) % 5);
        }, 500);

        return () => clearInterval(intId);
    }, [state]);


    useEffect(() => {
        if (state !== "loading") return;
        const timeoutId = setTimeout(() => setState("error"), 30000);
        return () => clearTimeout(timeoutId);
    }, [state]);


    return (
        <div className={`bottle-slot ${state}`}>
            {state === "loading" && (
                <div className="bottle-skeleton">
                    <img 
                    src={`${import.meta.env.BASE_URL}assets/logo-loading-${loaderInd + 1}.svg`} alt="" /> 
                </div>
            )}
            {state === "error" ? (
                <img src={`${import.meta.env.BASE_URL}assets/bottle-placeholder.png`} alt={alt} className="bottle-img" />
            ) : (
                <img
                    src={imageUrl(slug)}
                    alt={alt}
                    className="bottle-img"
                    style={{ visibility: state === "ready" ? "visible" : "hidden" }}
                    onLoad={() => setState("ready")}
                    onError={() => setState("error")}
                />
            )}
        </div>
    );
}


export default BottleImage;

