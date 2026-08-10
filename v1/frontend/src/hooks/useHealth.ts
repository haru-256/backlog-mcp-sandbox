import useSWR from "swr";

import { getHealth } from "../api";

export function useHealth() {
  return useSWR("health", getHealth, {
    refreshInterval: 10_000,
    shouldRetryOnError: true,
  });
}
