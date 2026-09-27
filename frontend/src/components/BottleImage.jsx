
import { useState } from "react";
import { imageUrl } from "../api.js";


function BottleImage({ slug, alt = "" }) {
    const [state, setState] = useState("loading");  // loading | ready | error

    return (
        <div className={`bottle-slot ${state}`}>
            {state === "loading" && <div className="bottle-skeleton">Загрузка</div>}
            {state === "error" ? 
            (
                <img src="../../public/assets/bottle-placeholder.png" alt={alt} className="bottle-img" />
            ) : (
                <img
                    src={imageUrl(slug)}
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