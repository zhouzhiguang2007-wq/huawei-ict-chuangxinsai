"""12306-mcp 联调自检。

启动 MCP server（默认 `npx -y 12306-mcp`），完成 stdio 握手与 tools/list，
核对必需工具是否齐全。用于在接入宿主前确认“工具真的能起来、能列出来”。

用法：
    python scripts/check_mcp.py
    python scripts/check_mcp.py --timeout 60
    python scripts/check_mcp.py --skip-network     # 只检查命令是否存在
    python scripts/check_mcp.py --json

退出码：0 可用；1 工具缺失或握手失败；2 运行环境缺失（找不到命令/参数错误）。

本脚本只做握手与工具枚举，不查询真实车次，不写任何数据。
"""

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

REQUIRED_TOOLS = (
    "get-current-date",
    "get-stations-code-in-city",
    "get-station-code-of-citys",
    "get-station-code-by-names",
    "get-station-by-telecode",
    "get-tickets",
)

DEFAULT_COMMAND = "npx"
DEFAULT_ARGS = ("-y", "12306-mcp")


def evaluate_tools(tool_names):
    """核对工具清单，返回结构化结果（纯函数，便于测试）。"""
    names = list(tool_names)
    missing = [t for t in REQUIRED_TOOLS if t not in names]
    return {
        "ok": not missing,
        "tool_count": len(names),
        "tools": names,
        "required": list(REQUIRED_TOOLS),
        "missing": missing,
    }


def _reader(stream, sink):
    try:
        for line in stream:
            text = line.decode("utf-8", "replace").strip()
            if text:
                sink.put(text)
    except Exception:
        pass


def _send(proc, message):
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    proc.stdin.flush()


def _wait_response(sink, request_id, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = sink.get(timeout=max(0.1, deadline - time.time()))
        except queue.Empty:
            return None
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if payload.get("id") == request_id:
            return payload
    return None


def probe(command=DEFAULT_COMMAND, args=DEFAULT_ARGS, timeout=90):
    """启动 MCP 并返回握手与工具清单。"""
    report = {
        "command": command,
        "args": list(args),
        "status": "unknown",
        "server": None,
        "tool_count": 0,
        "tools": [],
        "missing": list(REQUIRED_TOOLS),
        "error": None,
    }

    executable = shutil.which(command)
    if not executable:
        report["status"] = "missing_command"
        report["error"] = "找不到命令：{}（需要 Node.js 18+）".format(command)
        return report

    # Windows 上 npx 是 .cmd 批处理，CreateProcess 不能直接执行，需要走 shell。
    use_shell = os.name == "nt" and executable.lower().endswith((".cmd", ".bat"))
    try:
        proc = subprocess.Popen(
            [executable] + list(args),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0, shell=use_shell,
        )
    except OSError as exc:
        report["status"] = "spawn_failed"
        report["error"] = str(exc)
        return report

    sink = queue.Queue()
    thread = threading.Thread(target=_reader, args=(proc.stdout, sink), daemon=True)
    thread.start()

    try:
        _send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "check_mcp", "version": "1.0"}},
        })
        init = _wait_response(sink, 1, timeout)
        if not init or "result" not in init:
            report["status"] = "handshake_failed"
            report["error"] = "initialize 未返回 result"
            return report
        report["server"] = init["result"].get("serverInfo", {})

        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listing = _wait_response(sink, 2, timeout)
        if not listing or "result" not in listing:
            report["status"] = "tools_list_failed"
            report["error"] = "tools/list 未返回 result"
            return report

        names = [t.get("name") for t in listing["result"].get("tools", [])]
        evaluated = evaluate_tools(names)
        report.update(evaluated)
        report["status"] = "ok" if evaluated["ok"] else "missing_tools"
        return report
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="12306-mcp 联调自检")
    parser.add_argument("--command", default=DEFAULT_COMMAND)
    parser.add_argument("--arg", dest="args", action="append", default=None,
                        help="传给 MCP 的参数，可重复；默认 -y 12306-mcp")
    parser.add_argument("--timeout", type=int, default=90,
                        help="握手与 tools/list 的超时秒数")
    parser.add_argument("--skip-network", action="store_true",
                        help="只检查命令是否存在，不启动 MCP")
    parser.add_argument("--json", dest="as_json", action="store_true")
    args = parser.parse_args(argv)

    if args.args is None:
        args.args = list(DEFAULT_ARGS)

    if args.skip_network:
        report = {
            "command": args.command,
            "args": list(args.args),
            "status": "ok" if shutil.which(args.command) else "missing_command",
            "server": None, "tool_count": 0, "tools": [],
            "missing": list(REQUIRED_TOOLS),
            "error": None if shutil.which(args.command)
                     else "找不到命令：{}".format(args.command),
        }
    else:
        report = probe(args.command, args.args, args.timeout)

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("命令:", report["command"], " ".join(report["args"]))
        if report["server"]:
            print("服务端:", report["server"].get("name"),
                  report["server"].get("version"))
        print("状态:", report["status"])
        print("工具数:", report["tool_count"])
        if report["missing"]:
            print("缺少工具:", ", ".join(report["missing"]))
        if report["error"]:
            print("错误:", report["error"])

    if report["status"] == "missing_command":
        return 2
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())