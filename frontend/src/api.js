
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API = `${API_BASE}/api/v1`;


export function imageUrl(slug) {
  return `${API_BASE}/photos/${slug}.webp`;
}

// main recognize function
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

// wine card for frontend
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