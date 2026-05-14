"""获取无障碍树并保存到本地文件"""

import asyncio
import json
from datetime import datetime
from src.agentdesk_client import AgentDeskClient
from src.config import Config


async def main():
    config = Config()
    
    print(f"连接 AgentDesk: {config.agentdesk_host}:{config.agentdesk_port}")
    
    client = AgentDeskClient(
        host=config.agentdesk_host,
        port=config.agentdesk_port,
        token=config.agentdesk_token
    )
    
    try:
        # 检查服务是否可用
        if not await client.health_check():
            print("错误: AgentDesk 服务不可用")
            return
        
        print("服务正常，正在获取无障碍树...")
        
        # 获取无障碍树
        tree = await client.accessibility_tree(max_depth=10)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"accessibility_tree_{timestamp}.json"
        
        # 保存到文件
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False, indent=2)
        
        print(f"无障碍树已保存到: {filename}")
        print(f"文件大小: {len(json.dumps(tree))} 字符")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())