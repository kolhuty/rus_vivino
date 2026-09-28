
import "../styles/SearchResults.css";
import { useEffect, useState } from "react";

import Loading from "./Loading.jsx";
import WineCard from "./WineCard.jsx";
import { recognize } from "../api.js";


function SearchResults({ photo }) {
    /*
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    
    if (error) return <div className="search-error">{error}</div>;
    if (!result) return <Loading result={result} />;
    
    return <WineCard data={result} />;
    */




    
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);


    const MOCK = {
        status: "matched",
        main: { slug: "petrouchka", name: "Кокур сухое", producer: "Кокур", image_url: "" },
        others: [
            { slug: "golubitskoe-estate-chardonnay", name: "Рислинг", producer: "Фанагория", image_url: "" },
            { slug: "roze-premium", name: "Рислинг", producer: "Абрау-Дюрсо", image_url: "" },
            { slug: "krymskij-blend", name: "Рислинг", producer: "Абрау-Дюрсо", image_url: "" },
        ],
    };
    if (!result) return <WineCard data={MOCK} />;
    

    useEffect(() => {
        let cancelled = false;
        setResult(null);
        setError(null);

        recognize(photo)
            .then((data) => { if (!cancelled) setResult(data); })
            .catch(() => { if (!cancelled) setError("Не удалось распознать этикетку. Попробуйте ещё раз."); });

        return () => { cancelled = true; };
    }, [photo]);

    if (error) return <div className="search-error">{error}</div>;
    if (!result) return <Loading />;
    
    return <WineCard data={result} />;
    
}


export default SearchResults;