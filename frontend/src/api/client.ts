import axios from "axios";

function toSnake(str: string): string {
  return str.replace(/[A-Z]/g, (l) => "_" + l.toLowerCase());
}

export function toCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, l) => l.toUpperCase());
}

export function deepConvert(
  obj: unknown,
  convert: (k: string) => string
): unknown {
  if (Array.isArray(obj)) return obj.map((i) => deepConvert(i, convert));
  if (obj !== null && typeof obj === "object") {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        convert(k),
        deepConvert(v, convert),
      ])
    );
  }
  return obj;
}

export const client = axios.create({ baseURL: "http://localhost:8000" });

client.interceptors.request.use((config) => {
  if (config.data) {
    config.data = deepConvert(config.data, toSnake);
  }
  return config;
});

client.interceptors.response.use((response) => {
  response.data = deepConvert(response.data, toCamel);
  return response;
});
