import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { Type } from "typebox";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const execFileAsync = promisify(execFile);
const workspaceRoot = path.resolve(process.env.ROBOAGENT_WORKSPACE_ROOT ?? process.cwd());
const maxReadBytes = 200_000;
const maxToolResultChars = 6_000;

function resolveWorkspacePath(input: string): string {
	const resolved = path.resolve(workspaceRoot, input);
	const relative = path.relative(workspaceRoot, resolved);
	if (relative.startsWith(`..${path.sep}`) || relative === ".." || path.isAbsolute(relative)) {
		throw new Error(`Path is outside the RoboAgent workspace: ${input}`);
	}
	return resolved;
}

function textResult(text: string, details: Record<string, unknown> = {}) {
	const truncated = text.length > maxToolResultChars;
	const bounded = truncated ? `${text.slice(0, maxToolResultChars)}\n[tool result truncated; request a line range or narrower search]` : text;
	return { content: [{ type: "text" as const, text: bounded }], details: { ...details, truncated } };
}

async function collectFiles(directory: string, results: string[] = []): Promise<string[]> {
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		if ([".git", ".roboagent-runtime", "logs", "node_modules", "__pycache__", "RelWithDebInfo"].includes(entry.name)) continue;
		const fullPath = path.join(directory, entry.name);
		if (entry.isDirectory()) await collectFiles(fullPath, results);
		else results.push(path.relative(workspaceRoot, fullPath));
	}
	return results;
}

export function registerRoboAgentTools(pi: ExtensionAPI): void {
	pi.registerTool({
		name: "read_file",
		label: "Read file",
		description: "Read a UTF-8 text file inside the RoboAgent workspace.",
		promptSnippet: "read_file(path)",
		parameters: Type.Object({ path: Type.String(), startLine: Type.Optional(Type.Integer({ minimum: 1 })), endLine: Type.Optional(Type.Integer({ minimum: 1 })) }),
		async execute(_id, params) {
			const filePath = resolveWorkspacePath(params.path);
			const fileInfo = await stat(filePath);
			if (fileInfo.size > maxReadBytes) throw new Error(`File is larger than ${maxReadBytes} bytes.`);
			const lines = (await readFile(filePath, "utf8")).split(/\r?\n/);
			const start = Math.max(1, params.startLine ?? 1);
			const end = Math.min(lines.length, params.endLine ?? lines.length);
			if (end < start) throw new Error("endLine must be greater than or equal to startLine.");
			return textResult(lines.slice(start - 1, end).map((line, index) => `${start + index}: ${line}`).join("\n"), { path: params.path, bytes: fileInfo.size, startLine: start, endLine: end });
		},
	});

	pi.registerTool({
		name: "list_directory",
		label: "List directory",
		description: "List files and directories inside the RoboAgent workspace.",
		promptSnippet: "list_directory(path)",
		parameters: Type.Object({ path: Type.Optional(Type.String()) }),
		async execute(_id, params) {
			const directory = resolveWorkspacePath(params.path ?? ".");
			const entries = await readdir(directory, { withFileTypes: true });
			return textResult(entries.map((entry) => `${entry.isDirectory() ? "[dir] " : "      "}${entry.name}`).join("\n"));
		},
	});

	pi.registerTool({
		name: "search_files",
		label: "Search files",
		description: "Search UTF-8 text files inside the RoboAgent workspace for a string. Path may be a file or directory.",
		promptSnippet: "search_files(query, path?)",
		parameters: Type.Object({ query: Type.String(), path: Type.Optional(Type.String()) }),
		async execute(_id, params) {
			const searchPath = resolveWorkspacePath(params.path ?? ".");
			const searchInfo = await stat(searchPath);
			const files = searchInfo.isDirectory()
				? await collectFiles(searchPath)
				: [path.relative(workspaceRoot, searchPath)];
			const matches: string[] = [];
			for (const relativePath of files) {
				const filePath = path.join(workspaceRoot, relativePath);
				try {
					const content = await readFile(filePath, "utf8");
					content.split(/\r?\n/).forEach((line, index) => {
						if (line.toLowerCase().includes(params.query.toLowerCase())) matches.push(`${relativePath}:${index + 1}: ${line}`);
					});
				} catch { /* Ignore binary and unreadable files. */ }
				if (matches.length >= 200) break;
			}
			return textResult(matches.join("\n") || "No matches found.", { count: matches.length });
		},
	});

	for (const command of ["status", "diff", "log"] as const) {
		pi.registerTool({
			name: `get_git_${command}`,
			label: `Git ${command}`,
			description: `Show the current Git ${command} for the RoboAgent workspace.`,
			promptSnippet: `get_git_${command}()`,
			parameters: Type.Object({}),
			async execute() {
				try {
					const args = command === "log" ? ["log", "-8", "--oneline"] : [command, ...(command === "diff" ? ["--"] : [])];
					const result = await execFileAsync("git", args, { cwd: workspaceRoot, maxBuffer: 1_000_000 });
					return textResult(result.stdout || "Clean.");
				} catch (error) {
					const message = error instanceof Error ? error.message : String(error);
					return textResult(`Git command failed: ${message}`);
				}
			},
		});
	}

	if (process.env.ROBOAGENT_ENABLE_MUTATIONS === "1") {
		pi.registerTool({
			name: "write_file",
			label: "Write file",
			description: "Overwrite one UTF-8 workspace file with the supplied content. Explicitly enabled and always requires approval.",
			parameters: Type.Object({ path: Type.String(), content: Type.String() }),
			async execute(_id, params, _signal, _onUpdate, ctx) {
				if (!(await ctx.ui.confirm("Approve file write", params.path))) return textResult("Write cancelled by user.");
				await writeFile(resolveWorkspacePath(params.path), params.content, "utf8");
				return textResult(`Wrote ${params.path}.`);
			},
		});

		pi.registerTool({
			name: "apply_patch",
			label: "Apply patch",
			description: "Replace exactly one known text block in one workspace file. Requires approval and fails if the old text is absent.",
			parameters: Type.Object({ path: Type.String(), oldText: Type.String(), newText: Type.String() }),
			async execute(_id, params, _signal, _onUpdate, ctx) {
				if (!(await ctx.ui.confirm("Approve patch", params.path))) return textResult("Patch cancelled by user.");
				const filePath = resolveWorkspacePath(params.path);
				const content = await readFile(filePath, "utf8");
				if (!content.includes(params.oldText)) throw new Error("The exact oldText block was not found.");
				await writeFile(filePath, content.replace(params.oldText, params.newText), "utf8");
				return textResult(`Patched ${params.path}.`);
			},
		});

		pi.registerTool({
			name: "run_command",
			label: "Run command",
			description: "Run one validation, test, or build command in the RoboAgent workspace. Requires approval and rejects shell operators and destructive commands.",
			parameters: Type.Object({ command: Type.String() }),
			async execute(_id, params, _signal, _onUpdate, ctx) {
				if (/[;&|><]|\$\(|`|\b(remove-item|del|erase|format|shutdown|stop-process|git\s+(reset|clean|push))\b/i.test(params.command)) {
					throw new Error("Command contains a blocked shell operator or destructive operation.");
				}
				if (!(await ctx.ui.confirm("Approve command", params.command))) return textResult("Command cancelled by user.");
				const result = await execFileAsync("powershell.exe", ["-NoProfile", "-Command", params.command], { cwd: workspaceRoot, maxBuffer: 2_000_000 });
				return textResult(`${result.stdout}${result.stderr}`.trim() || "Command completed with no output.");
			},
		});
	}
}
