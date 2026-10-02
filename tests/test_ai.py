"""AI行为树 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.behavior_tree import BehaviorTree

class TestSequencerState:
    def test_sequencer_saves_node_state(self):
        bt = BehaviorTree()
        calls = []
        def node1(): calls.append("n1"); return "success"
        def node2(): calls.append("n2"); return "failure"
        bt.run_sequencer([node1, node2])
        assert "n1" in calls

class TestDecorator:
    def test_repeat_stops_on_failure(self):
        bt = BehaviorTree()
        def fail_node(): return "failure"
        result = bt.run_decorator(fail_node, "repeat")
        assert result == "failure"

class TestBlackboardTypes:
    def test_blackboard_type_check(self):
        bt = BehaviorTree()
        bt.blackboard["hp"] = "not_a_number"
        result = bt.blackboard_get("hp")
        assert isinstance(result, int)

class TestPathFollowing:
    def test_path_reached_with_tolerance(self):
        bt = BehaviorTree()
        path = [(10, 10), (20, 20)]
        result = bt.follow_path(path, (10.001, 10.001))
        assert result == True

class TestTargetSelection:
    def test_dead_target_not_selected(self):
        bt = BehaviorTree()
        enemies = [{"distance": 5, "alive": False}, {"distance": 10, "alive": True}]
        target = bt.select_target(enemies)
        assert target["alive"] == True
