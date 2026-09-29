
import "../styles/Loading.css";
import { useState, useEffect } from "react";


function Loading({ result }) {

    const [loaderInd, setLoaderInd] = useState(0);

    useEffect(() => {
        const intId = setInterval(() => {
            setLoaderInd((prevState) => prevState + 1);
        }, 500);

        return () => clearInterval(intId);
    }, [result]);

    return (
        <div id="loader-container">
            <img src={`${import.meta.env.BASE_URL}assets/logo-loading-${loaderInd % 5 + 1}.svg`} alt="" />
            <p>Загрузка...</p>
        </div>        
    )
}


export default Loading
