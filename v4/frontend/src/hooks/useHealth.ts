import useSWR from "swr";

import { getHealth } from "../api";

/**
 * Host の `/health` を定期的に取る。失敗は戻り値の error に入る。
 *
 * @returns SWR の data / error / isLoading。data.ok が true なら到達できている
 */
export function useHealth() {
  return useSWR("health", getHealth, {
    refreshInterval: 10_000,
    shouldRetryOnError: true,
  });
}
