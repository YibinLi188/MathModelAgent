/** 默认的 OpenAI Next Credits 配置。 */
export const OPENAI_NEXT_DEFAULTS = {
	apiType: "openai-responses",
	baseUrl: "https://api.openai-next.com/v1",
	modelId: "gpt-5.5",
	contextWindow: 128000,
} as const;
