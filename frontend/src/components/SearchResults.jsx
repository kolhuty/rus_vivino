
import "../styles/SearchResults.css";
import { useEffect, useState } from "react";

import Loading from "./Loading.jsx";
import WineCard from "./WineCard.jsx";
import { recognize } from "../api.js";


function SearchResults({ photo, onRetry }) {
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        recognize(photo)
            .then((data) => { if (!cancelled) setResult(data); })
            .catch(() => { if (!cancelled) setError("Не удалось распознать этикетку. Попробуйте ещё раз."); });

        return () => { cancelled = true; };
    }, [photo]);

    if (error) {
        return (
            <div className="search-error">
                <p>{error}</p>
                <button type="button" onClick={onRetry}>Выбрать другое фото</button>
            </div>
        );
    }
    if (!result) return <Loading />;
    
    return <WineCard data={result} />;
    
}


export default SearchResults;
