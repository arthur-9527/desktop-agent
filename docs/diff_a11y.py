#!/usr/bin/env python3
"""对比两次 AgentDesk 无障碍数据抓取结果。"""
import json, sys, os, glob
from pathlib import Path

DIR = Path(__file__).parent

def load_json(path):
    with open(path) as f:
        return json.load(f)

def compare_focused(f1, f2):
    """对比聚焦窗口信息"""
    a = load_json(f1)["element"]
    b = load_json(f2)["element"]

    print("=" * 50)
    print("  聚焦窗口对比")
    print("=" * 50)
    print(f"  第1次: [{a['role']}] {a['name']}")
    print(f"         bounds = {a['bounds']}")
    print(f"         子节点: {len(a.get('children', []))} 个")
    print()
    print(f"  第2次: [{b['role']}] {b['name']}")
    print(f"         bounds = {b['bounds']}")
    print(f"         子节点: {len(b.get('children', []))} 个")
    print()

    changed = []
    if a["role"] != b["role"]:
        changed.append(f"role: {a['role']} → {b['role']}")
    if a["name"] != b["name"]:
        changed.append(f"name: {a['name']} → {b['name']}")
    if a.get("bounds") != b.get("bounds"):
        changed.append(f"bounds: {a['bounds']} → {b['bounds']}")
    if changed:
        print("  >>> 变化:")
        for c in changed:
            print(f"      {c}")
    else:
        print("  >>> 无变化")
    print()

def compare_tree(f1, f2):
    """对比无障碍树"""
    t1 = load_json(f1)["tree"]
    t2 = load_json(f2)["tree"]

    print("=" * 50)
    print("  无障碍树顶层结构对比")
    print("=" * 50)

    def top_info(t):
        return {
            "role": t["role"],
            "name": t["name"],
            "bounds": t.get("bounds"),
            "children": len(t.get("children", [])),
            "roles": [c["role"] for c in t.get("children", [])],
        }

    i1, i2 = top_info(t1), top_info(t2)
    print(f"  第1次: {json.dumps(i1, ensure_ascii=False)}")
    print(f"  第2次: {json.dumps(i2, ensure_ascii=False)}")
    print()

    # 提取顶层窗口/面板列表
    print("=" * 50)
    print("  顶层窗口/面板列表")
    print("=" * 50)

    def top_windows(t, label):
        print(f"  --- {label} ---")
        for c in t.get("children", []):
            if c["role"] in ("Window", "Pane"):
                print(f"  [{c['role']:6}] {c['name'][:60]:60} @ {c.get('bounds', {})}")

    top_windows(t1, "第1次")
    print()
    top_windows(t2, "第2次")
    print()

    # 新增/移除的顶层窗口
    names1 = {c["name"] for c in t1.get("children", []) if c["role"] in ("Window", "Pane")}
    names2 = {c["name"] for c in t2.get("children", []) if c["role"] in ("Window", "Pane")}
    added = names2 - names1
    removed = names1 - names2
    if added:
        print(f"  新增窗口: {added}")
    if removed:
        print(f"  关闭窗口: {removed}")
    if not added and not removed:
        print("  顶层窗口列表无变化")
    print()

    # 统计
    def count_nodes(t):
        def walk(n):
            cnt = 1
            for child in n.get("children", []):
                cnt += walk(child)
            return cnt
        return walk(t)

    print("=" * 50)
    print("  统计")
    print("=" * 50)
    s1, s2 = os.path.getsize(f1), os.path.getsize(f2)
    n1, n2 = count_nodes(t1), count_nodes(t2)
    print(f"  文件大小:  {s1:>6} → {s2:<6} bytes  ({s2-s1:+d})")
    print(f"  元素节点:  {n1:>6} → {n2:<6} 个     ({n2-n1:+d})")

def main():
    # 自动发现文件
    trees = sorted(DIR.glob("accessibility_tree*.json"))
    if len(trees) < 2:
        print("需要至少两个 accessibility_tree*.json 文件")
        print(f"当前找到: {[t.name for t in trees]}")
        sys.exit(1)

    f1, f2 = trees[0], trees[-1]  # 默认对比最早和最新
    print(f"对比文件: {f1.name}  vs  {f2.name}")
    print(f"目录: {DIR}\n")

    # 自动匹配 focused 文件
    focus_pattern = str(f1).replace("accessibility_tree", "focused_window")
    if not os.path.exists(focus_pattern):
        focus_files = sorted(DIR.glob("focused_window*.json"))
        focus1 = focus_files[0] if focus_files else None
        focus2 = focus_files[-1] if focus_files else None
    else:
        focus1 = focus_pattern
        focus2 = str(f2).replace("accessibility_tree", "focused_window")

    if focus1 and focus2 and os.path.exists(str(focus1)) and os.path.exists(str(focus2)):
        compare_focused(str(focus1), str(focus2))
    else:
        print("未找到配对的 focused_window 文件，跳过聚焦窗口对比\n")

    compare_tree(str(f1), str(f2))

if __name__ == "__main__":
    main()
