
import { useState, useEffect } from "react";
import { imageUrl } from "../api.js";


function BottleImage({ slug, src, alt = "" }) {
    const [state, setState] = useState("loading");  // loading | ready | error
    const [loaderInd, setLoaderInd] = useState(0);

    useEffect(() => {
        if (state !== "loading") return;

        const intId = setInterval(() => {
            setLoaderInd((prevState) => prevState + 1);
        }, 500);

        return () => clearInterval(intId);
    }, [state]);

    return (
        <div className={`bottle-slot ${state}`}>
            {state === "loading" && <div className="bottle-skeleton">
                <img src={`/assets/logo-loading-${loaderInd % 5 + 1}.svg`} alt="" />
            </div>} 
            {state === "error" ? 
            (
                <img src="/assets/bottle-placeholder.png" alt={alt} className="bottle-img" />
            ) : (
                <img
                    src={src || imageUrl(slug)}
                    alt={alt}
                    style={{ visibility: state === "ready" ? "visible" : "hidden" }}
                    onLoad={() => setState("ready")}
                    onError={() => setState("error")}
                />
            )}
        </div>
    );
}

export default BottleImage;
