import type { paths } from "@api/schema.d.ts";
import createFetchClient from "openapi-fetch";
import createClient from "openapi-react-query";
import { apiBaseUrl, apiHeaders } from "~/platform/host";

const fetchClient = createFetchClient<paths>({
	baseUrl: apiBaseUrl,
	credentials: "include",
	headers: apiHeaders(),
});
export const $api = createClient(fetchClient);
