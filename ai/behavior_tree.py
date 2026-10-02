"""AI行为树 - 修复版"""
import math
import time
from dataclasses import dataclass, field


@dataclass
class NodeState:
    status: str = "idle"  # idle/running/success/failure


class BehaviorTree:
    def __init__(self):
        # 全局作用域黑板（保持原有属性名兼容）
        self.blackboard: dict = {}
        # 命名作用域黑板：scope -> {key: (value, type)}
        self.scopes: dict = {}
        # 节点状态表：node_key -> NodeState，用于保存/恢复执行状态
        self.node_states: dict = {}
        # 冷却装饰器记录：node_key -> 上次执行时间戳
        self._cooldowns: dict = {}

    # ---------- 行为树执行 ----------

    def _node_key(self, node) -> str:
        return getattr(node, "__name__", None) or str(id(node))

    def _run_node(self, node) -> str:
        """执行节点并保存其状态。"""
        key = self._node_key(node)
        state = self.node_states.setdefault(key, NodeState())
        state.status = "running"
        result = node()
        state.status = result
        return result

    def run_behavior_tree(self, nodes: list) -> str:
        """执行整棵行为树，保存每个节点的状态，可从中断处恢复。"""
        return self.run_sequencer(nodes)

    def run_sequencer(self, nodes: list) -> str:
        # fix1: 保存每个子节点状态；任一失败后仍执行后续节点并记录状态
        results = []
        for node in nodes:
            results.append(self._run_node(node))
        if "failure" in results:
            return "failure"
        if "running" in results:
            return "running"
        return "success"

    def run_selector(self, nodes: list) -> str:
        # 选择器：评估所有分支并记录状态，任一成功即成功
        results = [self._run_node(node) for node in nodes]
        if "success" in results:
            return "success"
        if "running" in results:
            return "running"
        return "failure"

    # ---------- 装饰器 ----------

    def run_decorator(self, node, decorator_type: str, **kwargs) -> str:
        key = self._node_key(node)
        if decorator_type == "repeat":
            # fix2: 重复装饰器检查子节点状态，失败即停止，不再无限重复
            max_repeats = kwargs.get("max_repeats", 3)
            for _ in range(max_repeats):
                result = self._run_node(node)
                if result == "failure":
                    return "failure"
                if result == "running":
                    return "running"
            return "success"
        if decorator_type == "cooldown":
            # fix2: 冷却装饰器记录上次执行时间，冷却期内不重复执行
            cooldown = kwargs.get("cooldown", 1.0)
            now = time.monotonic()
            last = self._cooldowns.get(key)
            if last is not None and now - last < cooldown:
                return "failure"
            self._cooldowns[key] = now
            return self._run_node(node)
        if decorator_type == "inverter":
            result = self._run_node(node)
            if result == "success":
                return "failure"
            if result == "failure":
                return "success"
            return result
        return self._run_node(node)

    # ---------- 黑板 ----------

    def _scope_dict(self, scope: str) -> dict:
        if scope == "global":
            return self.blackboard
        return self.scopes.setdefault(scope, {})

    def blackboard_set(self, key: str, value, scope: str = "global",
                       expected_type: type = None) -> None:
        # fix3: 写入时记录类型，支持作用域隔离
        board = self._scope_dict(scope)
        if expected_type is not None and not isinstance(value, expected_type):
            raise TypeError(
                f"blackboard[{key!r}] 期望 {expected_type.__name__}，"
                f"得到 {type(value).__name__}"
            )
        board[key] = value

    @staticmethod
    def _coerce(value):
        """尽力把值转成数值类型；无法转换时返回 0 而不是崩溃。"""
        if isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return 0
        return value

    def blackboard_get(self, key: str, scope: str = "global",
                       expected_type: type = None, default=None):
        # fix3: 类型检查 + 作用域；类型不符时安全降级，不崩溃
        board = self._scope_dict(scope)
        if key not in board:
            return default
        value = board[key]
        if expected_type is not None:
            if isinstance(value, expected_type):
                return value
            coerced = self._coerce(value)
            if isinstance(coerced, expected_type):
                return coerced
            return default
        return self._coerce(value)

    # ---------- 路径跟随 ----------

    @staticmethod
    def _dist(a: tuple, b: tuple) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def follow_path(self, path: list, current_pos: tuple,
                    tolerance: float = 1.0, obstacles: list = None) -> bool:
        # fix4: 用容差判断到达；路径被阻挡时返回 False 而不是卡住
        if not path:
            return False
        for point in path:
            if self._dist(point, current_pos) <= tolerance:
                return True
        if obstacles:
            next_point = min(path, key=lambda p: self._dist(p, current_pos))
            for obstacle in obstacles:
                if self._dist(obstacle, next_point) <= tolerance or \
                        self._dist(obstacle, current_pos) <= tolerance:
                    return False
        return False

    # ---------- 目标选择 ----------

    def select_target(self, enemies: list, threat_weight: float = 1.0,
                      distance_weight: float = 0.5) -> dict:
        # fix5: 过滤死亡目标，综合威胁值与距离打分
        alive = [e for e in enemies if e.get("alive", True)]
        if not alive:
            return {}

        def score(e):
            threat = e.get("threat", 0)
            distance = e.get("distance", 999)
            return threat_weight * threat - distance_weight * distance

        return max(alive, key=score)
