#!/usr/bin/env python3
"""
Symcio BrandOS × Lovart 品牌系統自動化 runner
- 依 brandos_brief.json 逐步呼叫 Lovart 官方 client（agent_skill.py）
- 狀態寫入 out/manifest.json，可中斷續跑（已完成步驟自動跳過）
- 遇到高成本確認（pending_confirmation）一律停下，不自動扣點

用法：
  export LOVART_ACCESS_KEY=ak_xxx LOVART_SECRET_KEY=sk_xxx
  python3 run_pipeline.py                 # 跑全部
  python3 run_pipeline.py --only 02_logo  # 只跑單步（重做）
  python3 run_pipeline.py --dry-run       # 只印出 prompt，不呼叫 API
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIENT = ROOT / "agent_skill.py"
OUT = ROOT / "out"
MANIFEST = OUT / "manifest.json"


def load_manifest():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"project_id": None, "threads": {}, "steps": {}}


def save_manifest(m):
    OUT.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2))


def call(args):
    """呼叫官方 client，回傳 stdout 最後一段 JSON。"""
    r = subprocess.run([sys.executable, "-I", str(CLIENT), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Lovart client 失敗 ({r.returncode}): {r.stderr.strip() or r.stdout.strip()}")
    out = r.stdout.strip()
    start = out.find("{")  # client 可能先印進度訊息
    return json.loads(out[start:])


def render(template, brief):
    return template.format(
        identity_core=brief["identity_core"],
        design_tokens=brief["design_tokens"],
        red_lines=brief["red_lines"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default=str(ROOT / "brandos_brief.json"))
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    brief = json.loads(Path(a.brief).read_text())
    m = load_manifest()

    if not a.dry_run:
        for k in ("LOVART_ACCESS_KEY", "LOVART_SECRET_KEY"):
            if not os.environ.get(k):
                sys.exit(f"缺少環境變數 {k}（Lovart 頭像選單 → AK/SK 管理）")
        if not m["project_id"]:
            m["project_id"] = call(["create-project"])["project_id"]
            call(["project-rename", "--project-id", m["project_id"], "--name", brief["project_name"]])
            save_manifest(m)
        print(f"Project: https://www.lovart.ai/canvas?projectId={m['project_id']}")

    for step in brief["steps"]:
        sid = step["id"]
        if a.only and sid != a.only:
            continue
        if not a.only and m["steps"].get(sid, {}).get("final_status") == "done":
            print(f"[skip] {sid}")
            continue

        prompt = render(step["prompt"], brief)
        if a.dry_run:
            print(f"\n=== {sid} ({step['mode']}, thread={step['thread']}) ===\n{prompt}")
            continue

        args = ["chat", "--prompt", prompt, "--json", "--download",
                "--output-dir", str(OUT / sid), "--project-id", m["project_id"]]
        tid = m["threads"].get(step["thread"])
        if tid:
            args += ["--thread-id", tid]
        else:
            args += ["--mode", step["mode"]]  # mode 只在 thread 首訊息生效
        if brief.get("brand_kit_id"):
            args += ["--kits", brief["brand_kit_id"]]
        refs = [d["url"] for src in step.get("attach_from", [])
                for d in m["steps"].get(src, {}).get("downloaded", []) if d.get("type") == "image"][:4]
        if refs:
            args += ["--attachments", *refs]

        print(f"[run ] {sid} …", flush=True)
        t0 = time.time()
        res = call(args)
        m["threads"].setdefault(step["thread"], res.get("thread_id"))
        m["steps"][sid] = {
            "thread_id": res.get("thread_id"),
            "final_status": res.get("final_status"),
            "generation_succeeded": res.get("generation_succeeded"),
            "failures": res.get("failures", []),
            "warning": res.get("warning"),
            "agent_text": [i.get("text") for i in res.get("items", []) if i.get("type") == "assistant"],
            "downloaded": res.get("downloaded", []),
            "seconds": round(time.time() - t0),
        }
        save_manifest(m)

        st = res.get("final_status")
        if st == "pending_confirmation":
            pc = res.get("pending_confirmation", {})
            sys.exit(f"[stop] {sid} 需確認高成本操作（約 {pc.get('estimated_cost', '?')} credits）。\n"
                     f"確認後執行：python3 agent_skill.py confirm --thread-id {res.get('thread_id')} --json --download "
                     f"--output-dir out/{sid}\n再重跑本程式續跑。")
        if st != "done":
            sys.exit(f"[stop] {sid} 狀態 {st}；稍後執行 result --thread-id {res.get('thread_id')} --json --download")
        if res.get("failures"):
            print(f"[warn] {sid}: {res.get('warning')}")
        n = len(res.get("downloaded", []))
        print(f"[done] {sid}: {n} 個檔案 → out/{sid}" + ("" if n or sid == "01_strategy" else "（無產出，見 manifest agent_text）"))

    if not a.dry_run:
        print(f"\n完成。Canvas：https://www.lovart.ai/canvas?projectId={m['project_id']}")


if __name__ == "__main__":
    main()
