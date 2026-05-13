import { useState, useEffect } from "react";

/**
 * 값이 변경된 후 delay ms 동안 안정화된 값을 반환.
 * 검색 input 디바운스에 사용.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return debouncedValue;
}
