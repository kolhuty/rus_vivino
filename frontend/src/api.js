
const API = "/api/v1";

export function imageUrl(slug) {
    return `${API}/images/by-slug/${slug}`;
}


export async function recognize(imageFile) {
    const formData = new FormData();
    formData.append("image", imageFile);

    const response = await fetch(`${API}/recognize`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        throw new Error(`Error: HTTP ${response.status}`);
    }

    return response.json();
}


// wien card fro frontend
export async function getWine(slug) {
    const response = await fetch(`${API}/wines/${slug}`);

    if (!response.ok) {
        throw new Error(`Вино не найдено: ${slug}`);
    }

    return response.json();
}


// backend health check
export async function isBackendAvailable() {
    try {
        const response = await fetch(`${API}/health`);
        const data = await response.json();
        return data.status === "ok";
    } catch {
        return false;
    }
}

