export type RoboAgentTurnPhase = "user" | "tool_result";

export const roboAgentToolNames = [
	"read_file",
	"list_directory",
	"search_files",
	"get_git_status",
	"get_git_diff",
	"write_file",
	"apply_patch",
	"run_command",
] as const;

export type RoboAgentToolName = (typeof roboAgentToolNames)[number];

export interface RoboAgentTurnRequest {
	protocol: "roboagent-pi/1";
	request_id: string;
	session_id: string;
	turn_id: number;
	phase: RoboAgentTurnPhase;
	prompt: string;
	system_prompt: string;
	seq_len: number;
	temperature: number;
	include_metrics: boolean;
	stream: boolean;
	tool_turn_limit: number;
}

export function createRoboAgentTurnRequest(input: Omit<RoboAgentTurnRequest, "protocol">): RoboAgentTurnRequest {
	return { protocol: "roboagent-pi/1", ...input };
}

export interface RoboAgentToolCallPayload {
	name: string;
	arguments: Record<string, unknown>;
}

export interface RoboAgentToolValidation {
	valid: boolean;
	reason?: string;
	call?: RoboAgentToolCallPayload;
}

export interface RoboAgentUsageMetrics {
	prompt_tokens?: number;
	generated_tokens?: number;
}

export interface RoboAgentTurnResponse {
	protocol?: "roboagent-pi/1";
	request_id?: string;
	kind?: "delta" | "tool_call" | "final" | "error";
	delta?: string;
	text?: string;
	ok?: boolean;
	error?: string;
	tool_call?: RoboAgentToolCallPayload;
	metrics?: RoboAgentUsageMetrics;
}

export function formatRoboAgentToolInstructions(toolNames: readonly string[]): string {
	return [
		`TOOLS: ${toolNames.join(", ")}`,
		"If the request needs a tool, output exactly one line and nothing else:",
		'<tool_call>{"name":"read_file","arguments":{"path":"README.md"}}</tool_call>',
		"Use one listed tool only. Arguments must be a JSON object.",
		"After a tool result, answer the user directly. Never call the same tool twice.",
	].join("\n");
}

export function validateRoboAgentToolCall(payload: unknown, availableTools: readonly string[]): RoboAgentToolValidation {
	if (!payload || typeof payload !== "object") return { valid: false, reason: "tool call must be an object" };
	const candidate = payload as { name?: unknown; arguments?: unknown };
	if (typeof candidate.name !== "string" || !candidate.name) return { valid: false, reason: "tool call name must be a non-empty string" };
	if (!availableTools.includes(candidate.name)) return { valid: false, reason: `unknown tool: ${candidate.name}` };
	if (!candidate.arguments || typeof candidate.arguments !== "object" || Array.isArray(candidate.arguments)) {
		return { valid: false, reason: "tool call arguments must be a JSON object" };
	}
	const args = candidate.arguments as Record<string, unknown>;
	if (candidate.name === "read_file" && typeof args.path !== "string") return { valid: false, reason: "read_file requires a string path" };
	if (candidate.name === "search_files" && typeof args.query !== "string") return { valid: false, reason: "search_files requires a string query" };
	if (["startLine", "endLine"].some((key) => key in args && (!Number.isInteger(args[key]) || Number(args[key]) < 1))) {
		return { valid: false, reason: "line ranges must be positive integers" };
	}
	return { valid: true, call: { name: candidate.name, arguments: args } };
}

export function parseRoboAgentToolCallText(text: string, availableTools: readonly string[]): RoboAgentToolValidation {
	const match = text.match(/<tool_call>\s*(\{[\s\S]*?\})\s*<\/tool_call>/i);
	if (!match) return { valid: false, reason: "no tool call found" };
	try {
		return validateRoboAgentToolCall(JSON.parse(match[1]), availableTools);
	} catch (error) {
		return { valid: false, reason: `malformed tool call JSON: ${error instanceof Error ? error.message : String(error)}` };
	}
}
