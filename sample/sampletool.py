from langchain_core.tools import tool
from typing import Optional, List
import json

# ==========================================
# 核心原则 (给开发者的 Note):
# 1. Docstring (文档字符串) 必须写清楚！Agent 靠读它来决定怎么用。
# 2. 参数必须有 Type Hint (类型提示)，否则 Agent 不知道怎么传参。
# 3. 永远不要抛出异常 (Raise Exception)，而是返回错误信息的字符串。
# ==========================================

@tool
def sampleTool(query: str, limit: int = 5) -> str: # 这个工具的名称是 sampleTool
    """
    [简短描述这个工具是干嘛的，例如：Search for relevant academic papers.]
    [什么时候用这个工具，例如：Use this tool when the user asks for scientific research.]
    
    Args:
        query (str): The search topic or question.
        limit (int): The max number of results to return. Default is 5.
    
    Returns:
        str: A formatted string containing the results or an error message.
    """
    
    # --- 1. 参数校验 (可选) ---
    if not query:
        return "Error: query parameter cannot be empty."

    try:
        # --- 2. 核心逻辑 (API 调用 / 计算) ---
        print(f"🔧 Tool Triggered: [tool_function_name] with query='{query}'")
        
        # 模拟业务逻辑 (Mock Logic)
        # result = your_api_call(query)
        result = {"data": f"Mock results for {query}", "count": limit}

        # --- 3. 格式化输出 ---
        # Agent 读 JSON 或者是清晰的文本效果最好
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        # --- 4. 兜底错误处理 ---
        # 哪怕代码崩了，也要告诉 Agent 发生了什么，而不是让程序 crash
        return f"Error executing tool: {str(e)}. Please try again with different parameters."














