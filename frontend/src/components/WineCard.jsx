
import "../styles/WineCard.css"
import BottleImage from "./BottleImage.jsx"


function WineCard({ data }) {
    const main = data.main
    const others = data.others
    
    const slug = main.slug;
    let link = slug;

    if ( !(/(?<!\d)20\d{2}(?!\d)/.test(main.name)) ) {  // if year (20XX) is NOT present in the wine name
        link = slug.split("-").filter((word) => !/^20\d{2}$/.test(word)).join("-");
    }  // so basically we check if year (year type 20XX) is not in the wine name and then remove the year from the link (because sometimes year is present in the slug but not the wine name) 

    return (
        <>
        <div id="navbar">
            <a href="https://vino-svoe.ru/" id="top-logo-container">
                <img src={`${import.meta.env.BASE_URL}assets/logo-full.svg`} id="top-logo"/>
            </a>
            <div id="nav-buttons">
                <button id="search" className="nav-button">
                    <span className="material-symbols-outlined">search</span>
                </button>
                <button id="menu" className="nav-button">
                    <span className="material-symbols-outlined">menu</span>
                </button>
            </div>
        </div>
        <div id="main">
            <div id="grid-wrapper">
                <div id="found">
                    <h1 id="found-wine">Найденное вино</h1>
                    <a id="found-wine-card" href={`https://vino-svoe.ru/wines/${link}`}>
                        <div id="found-wine-card-content">
                            <BottleImage
                                key={main.image_url || slug}
                                slug={slug}
                                src={main.image_url}
                                alt={main.name || slug || ""}
                            />
                            <h4>{main.name}</h4>
                            <p>{main.producer}</p>
                        </div>
                    </a>
                </div>
                <div id="sommelier-content">
                    <a href="/sommelier" id="sommelier-button">
                        <img src={`${import.meta.env.BASE_URL}assets/star-particles.svg`} alt="" />
                        <p>Цифровой сомелье</p>
                    </a>
                    <p>Узнайте, какое вино лучше всего подойдёт под ваши блюда или предпочтения</p>
                </div>
            </div>
            <div id="see-also">
                <h1 id="see-also-wine">Похожие</h1>
                <div id="see-also-container">
                    {others.map((wine, id) => {
                        let wineLink = wine.slug;
                        //console.log(wineLink);
                        if ( !(/(?<!\d)20\d{2}(?!\d)/.test(wine.name)) ) {
                            wineLink = wine.slug.split("-").filter((word) => !/^20\d{2}$/.test(word)).join("-");
                        }

                        return (
                        <a key={id} href={
                            `https://vino-svoe.ru/wines/${wineLink}`
                        } className="see-also-card-content">
                            <BottleImage
                                key={wine.image_url || wine.slug}
                                slug={wine.slug}
                                src={wine.image_url}
                                alt={wine.name || ""}
                            />
                            <h4>{wine.name}</h4>
                            <p>{wine.producer}</p>
                        </a>
                    )})}
                </div>
            </div>
        </div>
        <div id="footer">
            <div id="footer-first">
                <a href="https://forms.yandex.ru/cloud/6911d889e010db6b5d3f3410/">
                    Добавить винодельню в каталог
                </a>
                <a href="https://www.rshb.ru/pd-policy#cookie">
                    Политика использования Сookies
                </a>
                <a href="https://www.rshb.ru/pd-policy">Политика обработки персональных данных</a>
                <p>© Своё Вино, Россельхозбанк</p>
                <img src={`${import.meta.env.BASE_URL}assets/rshb-logo.svg`} alt="Россельхозбанк" />
            </div>
            <div id="footer-second">
                <p id="large-number">18+</p>
                <p>Чрезмерное употребление алкоголя вредит вашему здоровью</p>
            </div>
        </div>
        <div id="footer-nav-bar">
            <button id="footer-search" className="nav-button">
                <span className="material-symbols-outlined">search</span>
            </button>
            <p>Найти своё вино</p>
            <button id="footer-camera" className="nav-button" onClick={() => window.location.href="/"}>
                <span className="material-symbols-outlined">photo_camera</span>
            </button>
        </div>
        </>
    )
}


export default WineCard
