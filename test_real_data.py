"""真实数据测试 - 连接 AgentDesk 服务获取无障碍树"""

import asyncio
import httpx
from src.accessibility_parser import create_info_table


class RealClient:
    """简化的 AgentDesk 客户端"""

    def __init__(self, host: str = "localhost", port: int = 9877, token: str = "admin123"):
        self.base_url = f"http://{host}:{port}"
        self.auth = {"Authorization": f"Bearer {token}"}
        self._client = httpx.AsyncClient(timeout=30)

    async def accessibility_tree(self, max_depth: int = 10) -> dict:
        """获取无障碍树"""
        resp = await self._client.get(
            f"{self.base_url}/api/accessibility",
            params={"maxDepth": max_depth},
            headers=self.auth,
        )
        resp.raise_for_status()
        return resp.json()

    async def mouse_position(self) -> dict:
        """获取鼠标位置"""
        resp = await self._client.get(
            f"{self.base_url}/api/mouse/position",
            headers=self.auth,
        )
        resp.raise_for_status()
        return resp.json()

    async def accessibility_focused(self) -> dict:
        """获取焦点元素"""
        resp = await self._client.get(
            f"{self.base_url}/api/accessibility/focused",
            headers=self.auth,
        )
        resp.raise_for_status()
        return resp.json()

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            resp = await self._client.get(f"{self.base_url}/api/health")
            resp.raise_for_status()
            return resp.json().get("status") == "ok"
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()


async def main():
    print("=" * 60)
    print("真实数据测试 - 连接 AgentDesk 服务")
    print("=" * 60)

    client = RealClient()

    # 健康检查
    print("\n1. 检查服务状态...")
    try:
        healthy = await client.health_check()
        if not healthy:
            print("❌ AgentDesk 服务不可用，请确保服务已启动")
            await client.close()
            return
        print("✅ AgentDesk 服务正常")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        await client.close()
        return

    # 获取无障碍树
    print("\n2. 获取无障碍树 (max_depth=10)...")
    import time
    start = time.time()
    try:
        tree = await client.accessibility_tree(max_depth=10)
        elapsed = time.time() - start
        print(f"✅ 获取成功，耗时: {elapsed:.2f}s")
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        await client.close()
        return

    # 获取鼠标位置
    print("\n3. 获取鼠标位置...")
    try:
        mouse_pos = await client.mouse_position()
        print(f"✅ 鼠标位置: ({mouse_pos.get('x')}, {mouse_pos.get('y')})")
    except Exception as e:
        print(f"⚠️ 获取鼠标位置失败: {e}")
        mouse_pos = None

    # 获取焦点元素
    print("\n4. 获取焦点元素...")
    try:
        focused = await client.accessibility_focused()
        element = focused.get("element", {})
        print(f"✅ 焦点元素: [{element.get('role')}] {element.get('name')}")
    except Exception as e:
        print(f"⚠️ 获取焦点元素失败: {e}")
        focused = None

    # 生成信息表
    print("\n5. 生成全局动态信息表...")
    start = time.time()
    info_table = create_info_table(tree, mouse_pos, focused)
    elapsed = time.time() - start
    print(f"✅ 生成成功，耗时: {elapsed*1000:.2f}ms")

    print("\n" + "=" * 60)
    print("生成的全局动态信息表:")
    print("=" * 60)
    print(info_table)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())