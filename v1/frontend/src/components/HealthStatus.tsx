import { useHealth } from "../hooks/useHealth";

export function HealthStatus() {
  const { data, error, isLoading } = useHealth();

  let label = "checking…";
  if (error) {
    label = "unreachable";
  } else if (data?.ok) {
    label = "ok";
  } else if (!isLoading) {
    label = "not ok";
  }

  return (
    <p>
      API health: <strong>{label}</strong>
      {import.meta.env.VITE_API_BASE_URL
        ? ` (${import.meta.env.VITE_API_BASE_URL})`
        : " (VITE_API_BASE_URL unset)"}
    </p>
  );
}
