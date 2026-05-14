"""测试 KeyMapper 按键映射功能"""

from src.action_executor import KeyMapper


def test_key_mapper():
    """测试按键映射"""
    
    print("=" * 60)
    print("KeyMapper 测试")
    print("=" * 60)
    
    # 测试 Windows
    print("\n--- Windows 按键映射 ---")
    mapper_win = KeyMapper("Windows")
    
    test_cases = [
        (["ctrl", "c"], ["ControlLeft", "C"]),
        (["ctrl", "v"], ["ControlLeft", "V"]),
        (["ctrl", "shift", "s"], ["ControlLeft", "ShiftLeft", "S"]),
        (["alt", "tab"], ["AltLeft", "Tab"]),
        (["win", "d"], ["LeftWin", "D"]),
        (["win", "e"], ["LeftWin", "E"]),
        (["ctrl", "alt", "delete"], ["ControlLeft", "AltLeft", "Delete"]),
        (["f5"], ["F5"]),
        (["enter"], ["Enter"]),
        (["escape"], ["Escape"]),
        (["up"], ["ArrowUp"]),
        (["pageup"], ["PageUp"]),
        (["home"], ["Home"]),
    ]
    
    for raw_keys, expected in test_cases:
        result = mapper_win.normalize_keys(raw_keys)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {raw_keys} -> {result} (期望: {expected})")
    
    # 测试 macOS
    print("\n--- macOS 按键映射 ---")
    mapper_mac = KeyMapper("macOS")
    
    test_cases_mac = [
        (["cmd", "c"], ["LeftCmd", "C"]),
        (["cmd", "v"], ["LeftCmd", "V"]),
        (["cmd", "option", "esc"], ["LeftCmd", "AltLeft", "Escape"]),
        (["ctrl", "c"], ["ControlLeft", "C"]),
    ]
    
    for raw_keys, expected in test_cases_mac:
        result = mapper_mac.normalize_keys(raw_keys)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {raw_keys} -> {result} (期望: {expected})")
    
    # 测试 Linux
    print("\n--- Linux 按键映射 ---")
    mapper_linux = KeyMapper("Linux")
    
    test_cases_linux = [
        (["ctrl", "c"], ["ControlLeft", "C"]),
        (["super", "d"], ["MetaLeft", "D"]),
        (["win", "e"], ["MetaLeft", "E"]),
    ]
    
    for raw_keys, expected in test_cases_linux:
        result = mapper_linux.normalize_keys(raw_keys)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {raw_keys} -> {result} (期望: {expected})")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_key_mapper()