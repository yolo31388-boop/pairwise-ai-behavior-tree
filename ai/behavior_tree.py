"""AI行为树 - 含5个bug"""
from dataclasses import dataclass, field

@dataclass
class NodeState:
    status: str = "idle"  # idle/running/success/failure

class BehaviorTree:
    def __init__(self):
        self.blackboard: dict = {}  # bug3: 无类型检查无作用域
        self.node_states: dict = {}

    def run_sequencer(self, nodes: list) -> str:
        # bug1: 不保存节点状态，第一个失败就返回
        for node in nodes:
            result = node()
            if result == "failure":
                return "failure"
        return "success"

    def run_decorator(self, node, decorator_type: str) -> str:
        # bug2: 重复装饰器不检查子节点状态
        result = node()
        if decorator_type == "repeat":
            return "running"
        return result

    def blackboard_get(self, key: str):
        # bug3: 无类型检查
        return self.blackboard.get(key)

    def follow_path(self, path: list, current_pos: tuple) -> bool:
        # bug4: 精确相等判断
        for point in path:
            if point == current_pos:
                return True
        return False

    def select_target(self, enemies: list) -> dict:
        # bug5: 只选最近的，不检查存活
        if not enemies:
            return {}
        return min(enemies, key=lambda e: e.get("distance", 999))
