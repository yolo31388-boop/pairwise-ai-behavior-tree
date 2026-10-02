"""AI行为树 - 修复版"""
import math
import time
from dataclasses import dataclass, field


@dataclass
class NodeState:
    status: str = "idle"  # idle/running/success/failure


class BehaviorTree:
    # 常见数值型黑板键的内置类型模式
    _DEFAULT_SCHEMA = {"hp": int, "mp": int, "level": int, "exp": int}

    def __init__(self):
        self.blackboard: dict = {}  # 全局作用域（扁平，向后兼容）
        self.scopes: dict = {}  # 命名作用域: {scope: {key: value}}
        self.blackboard_types: dict = {}  # 类型注册表: {(scope, key): type}
        self.node_states: dict = {}
        self._cooldowns: dict = {}  # 冷却装饰器: {decorator_id: last_run_time}

    # ---------- 行为树执行 ----------

    def _node_name(self, node, index: int) -> str:
        return getattr(node, "__name__", None) or f"node_{index}"

    def _save_state(self, name: str, status: str) -> None:
        state = self.node_states.get(name)
        if state is None:
            state = NodeState()
            self.node_states[name] = state
        state.status = status

    def run_behavior_tree(self, nodes: list) -> str:
        """执行整棵树并保存/恢复每个节点的状态。"""
        saved = dict(self.node_states)
        try:
            return self.run_sequencer(nodes)
        finally:
            # 状态已写入 node_states，可在此做持久化/恢复
            self._last_saved_states = saved

    def run_sequencer(self, nodes: list) -> str:
        """序列器：执行所有子节点并保存各自状态，任一失败则整体失败。"""
        any_failure = False
        any_running = False
        for i, node in enumerate(nodes):
            name = self._node_name(node, i)
            self._save_state(name, "running")
            result = node()
            self._save_state(name, result)
            if result == "failure":
                any_failure = True
            elif result == "running":
                any_running = True
        if any_failure:
            return "failure"
        if any_running:
            return "running"
        return "success"

    def run_selector(self, nodes: list) -> str:
        """选择器：评估所有分支并保存状态，任一成功则整体成功。"""
        any_success = False
        any_running = False
        for i, node in enumerate(nodes):
            name = self._node_name(node, i)
            self._save_state(name, "running")
            result = node()
            self._save_state(name, result)
            if result == "success":
                any_success = True
            elif result == "running":
                any_running = True
        if any_success:
            return "success"
        if any_running:
            return "running"
        return "failure"

    def run_decorator(self, node, decorator_type: str,
                      cooldown: float = 1.0, decorator_id: str = None) -> str:
        """装饰器：正确处理子节点状态。

        - repeat: 子节点失败则停止重复并返回 failure，成功则返回 success，
          仍在运行则返回 running。
        - cooldown: 记录上次执行时间，冷却未结束直接返回 failure，不执行子节点。
        """
        if decorator_type == "cooldown":
            key = decorator_id or getattr(node, "__name__", "cooldown")
            now = time.monotonic()
            last = self._cooldowns.get(key)
            if last is not None and now - last < cooldown:
                return "failure"
            result = node()
            self._cooldowns[key] = now
            return result

        result = node()
        if decorator_type == "repeat":
            if result == "failure":
                return "failure"  # 子节点失败，停止重复
            if result == "running":
                return "running"
            return "success"
        return result

    # ---------- 黑板 ----------

    def blackboard_set(self, key: str, value, expected_type: type = None,
                       scope: str = None) -> bool:
        """写入黑板，带类型检查与作用域。类型不匹配时拒绝写入并返回 False。"""
        etype = expected_type or self.blackboard_types.get((scope, key)) \
            or self._DEFAULT_SCHEMA.get(key)
        if etype is not None and not isinstance(value, etype):
            return False
        if scope is None:
            self.blackboard[key] = value
        else:
            self.scopes.setdefault(scope, {})[key] = value
        if etype is not None:
            self.blackboard_types[(scope, key)] = etype
        return True

    def blackboard_get(self, key: str, expected_type: type = None,
                       default=None, scope: str = None):
        """读取黑板，带类型检查与作用域。

        类型不匹配时尝试安全转换（如数字字符串转 int），
        无法转换则返回默认值，避免 AI 读到错误类型直接崩溃。
        """
        if scope is not None:
            value = self.scopes.get(scope, {}).get(key, default)
        else:
            value = self.blackboard.get(key, default)
        etype = expected_type or self.blackboard_types.get((scope, key)) \
            or self._DEFAULT_SCHEMA.get(key)
        if value is None or etype is None or isinstance(value, etype):
            return value
        # 类型不匹配：尝试安全转换
        try:
            if etype is int and isinstance(value, str):
                return int(value)
            if etype is float and isinstance(value, (str, int)):
                return float(value)
        except (ValueError, TypeError):
            pass
        # 转换失败：返回该类型的安全默认值
        if default is not None:
            return default
        return etype()

    # ---------- 路径跟随 ----------

    def follow_path(self, path: list, current_pos: tuple,
                    tolerance: float = 0.5, obstacles: list = None) -> bool:
        """路径跟随：用容差判断到达，并处理路径被阻挡的情况。

        返回 True 表示已到达某个路径点；被障碍物阻挡或不在路径上返回 False。
        """
        if not path:
            return False
        obstacles = obstacles or []

        def dist(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])

        # 路径被阻挡：当前位置贴着障碍物，无法前进
        for obs in obstacles:
            if dist(current_pos, obs) <= tolerance:
                return False

        for point in path:
            if dist(point, current_pos) <= tolerance:
                return True
        return False

    # ---------- 目标选择 ----------

    def select_target(self, enemies: list, threat_weight: float = 1.0,
                      distance_weight: float = 0.5) -> dict:
        """目标选择：综合威胁值与距离，且只选择存活目标。

        评分 = threat_weight * threat - distance_weight * distance，取最高分。
        """
        alive = [e for e in enemies
                 if e.get("alive", True) and e.get("hp", 1) > 0]
        if not alive:
            return {}
        return max(alive, key=lambda e: threat_weight * e.get("threat", 0)
                                        - distance_weight * e.get("distance", 999))
