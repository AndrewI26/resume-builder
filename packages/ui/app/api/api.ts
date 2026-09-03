import type { paths } from "@api/schema.d.ts";
import createFetchClient from "openapi-fetch";
import createClient from "openapi-react-query";

const fetchClient = createFetchClient<paths>({
	baseUrl: import.meta.env.VITE_API_BASE_URL,
	credentials: "include",
});
export const $api = createClient(fetchClient);
