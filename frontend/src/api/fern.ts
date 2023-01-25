import { LotusApiClient } from "@lotus-fern/api";
import Cookies from "universal-cookie";

const cookies = new Cookies();

export const FERN_API_CLIENT = new LotusApiClient({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    environment: (import.meta as any).env.VITE_API_URL,
    authorization: () => `Token ${cookies.get("Token")}` 
})