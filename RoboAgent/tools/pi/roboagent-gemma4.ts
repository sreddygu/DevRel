import { createAssistantMessageEventStream, type AssistantMessage, type Context, type Model, type SimpleStreamOptions, type ToolCall } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import net from "node:net";
import { access, appendFile, mkdir, readFile, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { registerRoboAgentTools } from "./roboagent-tools.ts";
import { createRoboAgentTurnRequest, formatRoboAgentToolInstructions, parseRoboAgentToolCallText, roboAgentToolNames, validateRoboAgentToolCall, type RoboAgentTurnResponse, type RoboAgentUsageMetrics } from "./roboagent-protocol.ts";

const pipeName = process.env.ROBOAGENT_PIPE_NAME ?? "gemma4";
const pipePath = `\\\\.\\pipe\\${pipeName}`;
const workspaceRoot = process.env.ROBOAGENT_WORKSPACE_ROOT ?? process.cwd();
const runtimeDirectory = path.join(workspaceRoot, ".roboagent-runtime");
const logDirectory = process.env.ROBOAGENT_LOG_DIRECTORY ?? path.join(workspaceRoot, "logs");
const modelId = process.env.ROBOAGENT_MODEL_ID ?? "gemma4";
const modelName = process.env.ROBOAGENT_MODEL_NAME ?? "Gemma 4 (RoboAgent QNN)";
const contextBudget = Number(process.env.ROBOAGENT_CONTEXT_TOKENS ?? 3800);
const piContextWindow = Number(process.env.ROBOAGENT_PI_CONTEXT_TOKENS ?? 100_000);
const hostSequenceLength = Number(process.env.ROBOAGENT_HOST_SEQ_LEN ?? 3800);
const hostContextBudget = Math.min(contextBudget, hostSequenceLength);
const maxTokens = Number(process.env.ROBOAGENT_MAX_TOKENS ?? 1024);
const maxFollowUpChars = 6_000;
const maxSystemPromptChars = 4_000;
const recoveryReadyTimeoutMs = 100_000;
const responseInstruction = [
	"Answer general knowledge questions directly using your own knowledge.",
	"For common abbreviations, give the common technical meaning before asking for project-specific context.",
	"Treat informal questions as general knowledge unless they explicitly ask for current, live, or local conditions.",
	"For a general question, provide a useful answer instead of saying that you cannot personally observe the subject.",
	"Use workspace tools only when the answer needs project files, repository state, or other local evidence.",
	"Do not claim that you need more project context for a common question when you can answer it directly.",
	"Respond only in English. Do not use words, sentences, headings, tables, translations, or examples in any other language.",
	"When details are missing, state reasonable assumptions and give a useful plan in English instead of asking unnecessary clarifying questions.",
].join(" ");
const turnInstruction = "IMPORTANT: Write the entire response in English only. Do not use any other language. Answer the user's request directly; if details are missing, state assumptions and provide a useful English plan.";
let hostConversationInitialized = false;
let estimatedContextTokens = 0;
let toolTurns = 0;
let lastUserPrompt = "";
const sessionId = process.env.ROBOAGENT_SESSION_ID ?? randomUUID();
let turnId = 0;
let requestId = 0;
let sharedSocket: net.Socket | undefined;
let sharedBuffer = "";
const queuedLines: string[] = [];
const lineWaiters: Array<(line: string) => void> = [];

async function traceProtocol(entry: Record<string, unknown>): Promise<void> {
	if (process.env.ROBOAGENT_DEBUG_PROTOCOL !== "1") return;
	await mkdir(logDirectory, { recursive: true });
	const tracePath = path.join(logDirectory, "pi-protocol.jsonl");
	await appendFile(tracePath, `${JSON.stringify({ timestamp: new Date().toISOString(), ...entry })}\n`);
}

function latestUserText(context: Context): string {
	for (let index = context.messages.length - 1; index >= 0; index -= 1) {
		const message = context.messages[index];
		if (message.role !== "user") {
			continue;
		}
		if (typeof message.content === "string") {
			return message.content;
		}
		return message.content
			.filter((part): part is { type: "text"; text: string } => part.type === "text")
			.map((part) => part.text)
			.join("\n");
	}
	return "";
}

function latestToolResult(context: Context): string | undefined {
	const message = context.messages.at(-1);
	if (!message || message.role !== "toolResult") return undefined;
	return message.content.filter((part): part is { type: "text"; text: string } => part.type === "text").map((part) => part.text).join("\n");
}

function messageText(context: Context): string {
	const parts: string[] = [];
	for (const message of context.messages) {
		if (message.role === "user" || message.role === "assistant") {
			const text = typeof message.content === "string"
				? message.content
				: message.content.filter((part): part is { type: "text"; text: string } => part.type === "text").map((part) => part.text).join("\n");
			if (text) parts.push(`${message.role.toUpperCase()}: ${text}`);
		}
	}
	return parts.join("\n\n");
}

function cleanModelText(text: string): string {
	return text.replaceAll("<turn|>", "").trimEnd();
}

function containsNonEnglishOutput(text: string): boolean {
	if (/[^\u0000-\u024f\u1e00-\u1eff\u2000-\u206f\u20a0-\u20cf]/u.test(text)) return true;
	return /\b(?:por favor|preciso de|não|nao|forneça|forneca|baixar o modelo|plano de alto nível|plano de alto nivel|passo a passo|ambiente de execução|ambiente de execucao)\b/i.test(text);
}

function enforceEnglishOnly(text: string): string {
	if (!containsNonEnglishOutput(text)) return text;
	return "The local model produced non-English text, so this response was suppressed. Please send the request again; the English-only instruction is now included with every turn.";
}

function estimateTokens(text: string): number {
	return Math.ceil(text.length / 4);
}

function toolInstructions(context: Context): string {
	const tools = context.tools?.length ? context.tools.map((tool) => tool.name) : process.env.ROBOAGENT_READ_ONLY_TOOLS === "1" ? roboAgentToolNames.slice(0, 5) : [];
	if (!tools.length) return "";
	return `\n\n${formatRoboAgentToolInstructions(tools)}`;
}

function toolNames(context: Context): string[] {
	return context.tools?.length ? context.tools.map((tool) => tool.name) : roboAgentToolNames.slice(0, 5);
}

async function recoverHost(): Promise<void> {
	if (process.env.ROBOAGENT_ALLOW_HOST_RESTART !== "1") throw new Error("RoboAgent context budget exhausted; host restart is disabled. Set ROBOAGENT_ALLOW_HOST_RESTART=1 to enable recovery.");
	const script = fileURLToPath(new URL("./restart-roboagent-host.ps1", import.meta.url));
	sharedSocket?.destroy();
	sharedSocket = undefined;
	sharedBuffer = "";
	queuedLines.length = 0;
	const readyFile = path.join(runtimeDirectory, `host-ready-${pipeName}.txt`);
	const recoveryLog = path.join(logDirectory, `host-recovery-${pipeName}.log`);
	const hostLog = path.join(logDirectory, "host.stderr.log");
	await rm(readyFile, { force: true });
	const restart = spawn("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-PipeName", pipeName, "-SeqLen", String(hostSequenceLength)], {
		cwd: process.cwd(),
		windowsHide: true,
		stdio: "ignore",
	});
	let restartError: Error | undefined;
	let restartExited = false;
	let restartExitCode: number | null = null;
	let restartSignal: NodeJS.Signals | null = null;
	restart.once("error", (error) => {
		restartError = error;
	});
	restart.once("exit", (code, signal) => {
		restartExited = true;
		restartExitCode = code;
		restartSignal = signal;
	});
	const readTail = async (file: string): Promise<string> => {
		try {
			return (await readFile(file, "utf8")).trim().split(/\r?\n/).slice(-16).join("\n");
		} catch {
			return "No diagnostic log was written.";
		}
	};
	const deadline = Date.now() + recoveryReadyTimeoutMs;
	for (;;) {
		try {
			await access(readyFile);
			break;
		} catch {
			if (restartError) {
				throw new Error(`RoboAgent host recovery process could not start: ${restartError.message}`);
			}
			if (restartExited) {
				const recoveryTail = await readTail(recoveryLog);
				throw new Error(`RoboAgent host recovery process exited before readiness (code ${restartExitCode ?? "none"}, signal ${restartSignal ?? "none"}).\nRecovery status:\n${recoveryTail}`);
			}
			if (Date.now() >= deadline) {
				const [recoveryTail, hostTail] = await Promise.all([readTail(recoveryLog), readTail(hostLog)]);
				throw new Error(`RoboAgent host did not report readiness within ${Math.round(recoveryReadyTimeoutMs / 1000)} seconds after context recovery: ${readyFile}\nRecovery status:\n${recoveryTail}\nHost log:\n${hostTail}`);
			}
			await new Promise((resolve) => setTimeout(resolve, 500));
		}
	}
	hostConversationInitialized = false;
	estimatedContextTokens = 0;
	toolTurns = 0;
}

function metricCount(value: number | undefined): number {
	return typeof value === "number" && Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

function usageFromMetrics(metrics?: RoboAgentUsageMetrics): AssistantMessage["usage"] {
	const input = metricCount(metrics?.prompt_tokens);
	const output = metricCount(metrics?.generated_tokens);
	return {
		input,
		output,
		cacheRead: 0,
		cacheWrite: 0,
		totalTokens: input + output,
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
	};
}

function contextTokensForTurn(metrics: RoboAgentUsageMetrics | undefined, fallback: number): number {
	const usage = usageFromMetrics(metrics);
	return usage.totalTokens || fallback;
}

function tokenSummary(metrics: RoboAgentUsageMetrics | undefined, contextTokens: number): string {
	const usage = usageFromMetrics(metrics);
	if (!usage.totalTokens) return "";
	const used = Math.min(hostContextBudget, Math.max(0, contextTokens));
	const available = Math.max(0, hostContextBudget - used);
	return `\n\nTokens used: input ${usage.input} | output ${usage.output} | total ${usage.totalTokens}\nQNN context: used ${used} / ${hostContextBudget} | available ${available}`;
}

function createMessage(model: Model<any>, text: string, stopReason: "stop" | "error", errorMessage?: string, metrics?: RoboAgentUsageMetrics): AssistantMessage {
	return {
		role: "assistant",
		content: [{ type: "text", text }],
		api: model.api,
		provider: model.provider,
		model: model.id,
		usage: usageFromMetrics(metrics),
		stopReason,
		errorMessage,
		timestamp: Date.now(),
	};
}

async function connectRoboAgentPipe(): Promise<net.Socket> {
	if (sharedSocket && !sharedSocket.destroyed) return sharedSocket;
	let lastError: unknown;
	for (let attempt = 0; attempt < 20; attempt += 1) {
		let socket: net.Socket | undefined;
		try {
			socket = net.createConnection(pipePath);
			await new Promise<void>((resolve, reject) => {
				const timeout = setTimeout(() => {
					socket?.destroy();
					reject(new Error(`Timed out connecting to RoboAgent pipe after 2,000 ms: ${pipePath}`));
				}, 2_000);
				socket.once("connect", () => {
					clearTimeout(timeout);
					resolve();
				});
				socket.once("error", (error) => {
					clearTimeout(timeout);
					reject(error);
				});
			});
			socket.setEncoding("utf8");
			socket.on("data", (chunk: string) => {
				sharedBuffer += chunk;
				const lines = sharedBuffer.split("\n");
				sharedBuffer = lines.pop() ?? "";
				for (const line of lines) {
					if (!line.trim()) continue;
					const waiter = lineWaiters.shift();
					if (waiter) waiter(line.trim());
					else queuedLines.push(line.trim());
				}
			});
			socket.on("close", () => {
				sharedSocket = undefined;
				sharedBuffer = "";
			});
			sharedSocket = socket;
			return socket;
		} catch (error) {
			socket?.destroy();
			lastError = error;
			await new Promise((resolve) => setTimeout(resolve, 250));
		}
	}
	const detail = lastError instanceof Error ? lastError.message : String(lastError);
	throw new Error(`Unable to connect to the RoboAgent host at ${pipePath}. Start Pi with .\\tools\\pi\\start-roboagent-pi.ps1, or start qnn_llm_host.exe before running pi directly. Last connection error: ${detail}`);
}

function readPipeLine(timeoutMs = 120_000): Promise<string> {
		const queued = queuedLines.shift();
		if (queued) return Promise.resolve(queued);
		return new Promise((resolve, reject) => {
			const waiter = (line: string) => {
				clearTimeout(timer);
				resolve(line);
			};
			const timer = setTimeout(() => {
				const index = lineWaiters.indexOf(waiter);
				if (index >= 0) lineWaiters.splice(index, 1);
			reject(new Error(`Timed out waiting for RoboAgent response after ${timeoutMs} ms.`));
			}, timeoutMs);
			lineWaiters.push(waiter);
		});
}

function requestSequenceLength(requestTokens: number): number {
	return Math.min(hostSequenceLength, Math.max(1, estimatedContextTokens + requestTokens + maxTokens));
}

function streamRoboAgent(model: Model<any>, context: Context, options?: SimpleStreamOptions) {
	const stream = createAssistantMessageEventStream();
	const latestPrompt = latestUserText(context);
	const toolResult = latestToolResult(context);
	if (latestPrompt && latestPrompt !== lastUserPrompt) {
		lastUserPrompt = latestPrompt;
		toolTurns = 0;
	}
	let prompt = toolResult
		? `${turnInstruction}\n\nTOOL RESULT:\n${toolResult.slice(0, maxFollowUpChars)}\n\nAnswer the user directly using this result. Do not request another tool.`
		: `${turnInstruction}\n\nUSER REQUEST:\n${hostConversationInitialized ? latestPrompt : messageText(context)}`;
	if (!toolResult && !hostConversationInitialized) prompt = prompt.slice(-maxFollowUpChars);
	const temperature = options?.temperature ?? 0;
	const toolsEnabled = process.env.ROBOAGENT_READ_ONLY_TOOLS === "1" || Boolean(context.tools?.length);
	const requestStreaming = !toolsEnabled || Boolean(toolResult && toolTurns > 0);
	const systemPrompt = `${context.systemPrompt ?? ""}${toolInstructions(context)}\n\n${responseInstruction}`.slice(0, maxSystemPromptChars);

	void (async () => {
		if (!prompt) {
			const message = createMessage(model, "", "error", "RoboAgent received an empty user prompt.");
			stream.push({ type: "error", reason: "error", error: message });
			stream.end(message);
			return;
		}
		const sendsSystemPrompt = !hostConversationInitialized;
		let requestTokens = estimateTokens(prompt) + (sendsSystemPrompt ? estimateTokens(systemPrompt) : 0);
		if (estimatedContextTokens + requestTokens + maxTokens > hostContextBudget) {
			try {
				await traceProtocol({ direction: "recovery", reason: "context_budget", estimated_tokens: estimatedContextTokens + requestTokens + maxTokens, budget: hostContextBudget, response_reserve: maxTokens });
				await recoverHost();
				prompt = `RECENT CONTEXT REPLAY:\n${messageText(context).slice(-maxFollowUpChars)}\n\nContinue the user's latest request directly. Use only the recent context above; older conversation turns were removed to free QNN context.\n\n${responseInstruction}`;
				requestTokens = estimateTokens(prompt);
				if (requestTokens + maxTokens > hostContextBudget) {
					throw new Error(`RoboAgent request is too large after context trimming. Shorten the latest request or start a fresh Pi session.`);
				}
			} catch (error) {
				const message = createMessage(model, "", "error", error instanceof Error ? error.message : String(error));
				stream.push({ type: "error", reason: "error", error: message });
				stream.end(message);
				return;
			}
		}
		const sequenceLength = requestSequenceLength(requestTokens);

		const partial = createMessage(model, "", "stop");
		stream.push({ type: "start", partial });
		if (requestStreaming) {
			stream.push({ type: "text_start", contentIndex: 0, partial });
		}

		let text = "";
		let metrics: RoboAgentUsageMetrics | undefined;
		let finished = false;
		let socket: net.Socket | undefined;
		try {
			socket = await connectRoboAgentPipe();
			const currentRequestId = `${sessionId}-${++requestId}`;
			const request = createRoboAgentTurnRequest({
				request_id: currentRequestId,
				session_id: sessionId,
				turn_id: ++turnId,
				phase: toolResult ? "tool_result" : "user",
				prompt,
				system_prompt: sendsSystemPrompt ? systemPrompt : "",
				seq_len: sequenceLength,
				temperature,
				include_metrics: true,
				stream: requestStreaming,
				tool_turn_limit: 1,
			});
			socket.write(`${JSON.stringify(request)}\n`);
			await traceProtocol({ direction: "request", ...request, prompt_chars: prompt.length });

			while (!finished) {
				const response = JSON.parse(await readPipeLine()) as RoboAgentTurnResponse;
				if (response.metrics) metrics = response.metrics;
				await traceProtocol({ direction: "response", kind: response.kind, ok: response.ok, response_chars: response.text?.length ?? response.delta?.length ?? 0, prompt_tokens: response.metrics?.prompt_tokens, generated_tokens: response.metrics?.generated_tokens });
				if (response.request_id && response.request_id !== currentRequestId) {
					throw new Error(`RoboAgent response request_id mismatch: expected ${currentRequestId}, received ${response.request_id}.`);
				}
				if (response.kind === "delta" || response.delta) {
					text += response.delta ?? "";
					if (requestStreaming) {
						partial.content = [{ type: "text", text: cleanModelText(text) }];
						stream.push({ type: "text_delta", contentIndex: 0, delta: response.delta, partial });
					}
					continue;
				}
				if (response.kind === "error" || response.ok === false) {
					finished = true;
					const message = createMessage(model, text, "error", response.error ?? "RoboAgent request failed.", metrics);
					stream.push({ type: "text_end", contentIndex: 0, content: text, partial: message });
					stream.push({ type: "error", reason: "error", error: message });
					stream.end(message);
					break;
				}
				if (response.kind === "tool_call" && response.tool_call) {
					const validatedCall = validateRoboAgentToolCall(response.tool_call, toolNames(context));
					if (!validatedCall.valid || !validatedCall.call) {
						await traceProtocol({ direction: "tool_call", status: "invalid", reason: validatedCall.reason });
						throw new Error(`Invalid RoboAgent tool call: ${validatedCall.reason}`);
					}
					if (toolTurns >= 1) {
						await traceProtocol({ direction: "tool_call", status: "repeated", name: validatedCall.call.name, arguments: validatedCall.call.arguments });
						throw new Error(`Repeated RoboAgent tool call: ${validatedCall.call.name}`);
					}
					const toolCall: ToolCall = {
						type: "toolCall",
						id: `roboagent-${Date.now()}`,
						name: validatedCall.call.name,
						arguments: validatedCall.call.arguments,
					};
					await traceProtocol({ direction: "tool_call", status: "valid", name: toolCall.name, arguments: toolCall.arguments });
					toolTurns += 1;
					finished = true;
					const toolMessage = createMessage(model, "", "stop", undefined, metrics);
					toolMessage.content = [toolCall];
					toolMessage.stopReason = "toolUse";
					stream.push({ type: "toolcall_start", contentIndex: 0, partial: toolMessage });
					stream.push({ type: "toolcall_end", contentIndex: 0, toolCall, partial: toolMessage });
					stream.push({ type: "done", reason: "toolUse", message: toolMessage });
					stream.end(toolMessage);
					hostConversationInitialized = true;
					estimatedContextTokens += requestTokens;
					break;
				}
				if (response.kind === "final" || response.ok === true) {
					finished = true;
					if (response.text && !text) {
						text = response.text;
						if (requestStreaming) {
							partial.content = [{ type: "text", text: cleanModelText(text) }];
							stream.push({ type: "text_delta", contentIndex: 0, delta: text, partial });
						}
					}
					text = cleanModelText(text);
					const parsedToolCall = parseRoboAgentToolCallText(text, toolNames(context));
					const hasToolMarkup = /<tool_call>/i.test(text);
					if (hasToolMarkup && !parsedToolCall.valid) {
						await traceProtocol({ direction: "tool_call", status: "invalid", reason: parsedToolCall.reason, text });
						throw new Error(`Invalid RoboAgent tool call: ${parsedToolCall.reason}`);
					}
					if (parsedToolCall.valid && parsedToolCall.call && toolTurns < 1) {
						const toolCall: ToolCall = { type: "toolCall", id: `roboagent-${Date.now()}`, name: parsedToolCall.call.name, arguments: parsedToolCall.call.arguments };
						await traceProtocol({ direction: "tool_call", status: "valid", name: toolCall.name, arguments: toolCall.arguments });
						toolTurns += 1;
					const toolMessage = createMessage(model, "", "stop", undefined, metrics);
						toolMessage.content = [toolCall];
						toolMessage.stopReason = "toolUse";
						stream.push({ type: "toolcall_start", contentIndex: 0, partial: toolMessage });
						stream.push({ type: "toolcall_end", contentIndex: 0, toolCall, partial: toolMessage });
						stream.push({ type: "done", reason: "toolUse", message: toolMessage });
						stream.end(toolMessage);
						hostConversationInitialized = true;
						estimatedContextTokens += requestTokens + estimateTokens(text);
						break;
					}
					if (parsedToolCall.valid && parsedToolCall.call && toolTurns >= 1) {
						await traceProtocol({ direction: "tool_call", status: "repeated", name: parsedToolCall.call.name, arguments: parsedToolCall.call.arguments });
						throw new Error(`Repeated RoboAgent tool call: ${parsedToolCall.call.name}`);
					}
					const modelText = enforceEnglishOnly(cleanModelText(text));
					const nextContextTokens = Math.min(
						hostContextBudget,
						estimatedContextTokens + contextTokensForTurn(metrics, requestTokens + estimateTokens(modelText)),
					);
					const usageText = tokenSummary(metrics, nextContextTokens);
					const displayText = `${modelText}${usageText}`;
					const message = createMessage(model, displayText, "stop", undefined, metrics);
					await traceProtocol({ direction: "final", text: modelText, prompt_tokens: message.usage.input, generated_tokens: message.usage.output, grounded: Boolean(toolResult && modelText && toolResult.toLowerCase().split(/\W+/).some((word) => word.length > 4 && modelText.toLowerCase().includes(word))) });
					if (requestStreaming && usageText) {
						partial.content = [{ type: "text", text: displayText }];
						stream.push({ type: "text_delta", contentIndex: 0, delta: usageText, partial });
					}
					stream.push({ type: "text_end", contentIndex: 0, content: displayText, partial: message });
					stream.push({ type: "done", reason: "stop", message });
					stream.end(message);
					hostConversationInitialized = true;
					estimatedContextTokens = nextContextTokens;
					if (socket && !socket.destroyed) {
						socket.end();
						sharedSocket = undefined;
					}
					break;
				}
			}
		} catch (error) {
			const message = createMessage(model, text, "error", error instanceof Error ? error.message : String(error));
			stream.push({ type: "error", reason: "error", error: message });
			stream.end(message);
			if (socket && socket.destroyed) sharedSocket = undefined;
		}
	})();

	return stream;
}

export default function (pi: ExtensionAPI) {
	registerRoboAgentTools(pi);
	pi.on("session_start", () => {
		hostConversationInitialized = false;
		estimatedContextTokens = 0;
	toolTurns = 0;
	lastUserPrompt = "";
	turnId = 0;
	});
	pi.registerProvider("roboagent", {
		name: `RoboAgent ${modelName}`,
		baseUrl: "http://127.0.0.1",
		api: "openai-completions",
		apiKey: "ROBOAGENT_LOCAL",
		models: [{
			id: modelId,
			name: modelName,
			reasoning: false,
			input: ["text"],
			cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
			contextWindow: piContextWindow,
			maxTokens,
		}],
		streamSimple: streamRoboAgent,
	});
}
