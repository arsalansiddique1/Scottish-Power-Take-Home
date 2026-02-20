from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from review_agent.agents.delegation_manager import DelegationManager
from review_agent.agents.refactoring_agent import RefactoringAgent
from review_agent.agents.verification_agent import VerificationAgent
from review_agent.models import ChangedFile, DelegationDecision, Finding, RefactorAction, VerificationResult


class AgentGraphState(TypedDict):
    changed_files: list[ChangedFile]
    findings: list[Finding]
    delegation_decision: DelegationDecision
    refactor_actions: list[RefactorAction]
    verification_result: VerificationResult
    handoff_log: list[str]


class DelegationGraphRunner:
    def __init__(
        self,
        delegation_manager: DelegationManager,
        refactoring_agent: RefactoringAgent | None = None,
        verification_agent: VerificationAgent | None = None,
    ) -> None:
        self._delegation_manager = delegation_manager
        self._refactoring_agent = refactoring_agent or RefactoringAgent()
        self._verification_agent = verification_agent or VerificationAgent()
        self._graph = self._build_graph()

    def run(
        self,
        changed_files: list[ChangedFile],
        findings: list[Finding],
        graph_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        initial_state: AgentGraphState = {
            "changed_files": changed_files,
            "findings": findings,
            "delegation_decision": DelegationDecision(should_delegate=False, reasons=[]),
            "refactor_actions": [],
            "verification_result": VerificationResult(passed=True, details=[]),
            "handoff_log": [],
        }
        return self._graph.invoke(initial_state, config=graph_config or {})

    def _build_graph(self):
        graph = StateGraph(AgentGraphState)

        graph.add_node("decide_delegation", self._decide_delegation)
        graph.add_node("run_refactor", self._run_refactor)
        graph.add_node("run_verification", self._run_verification)

        graph.set_entry_point("decide_delegation")
        graph.add_conditional_edges(
            "decide_delegation",
            self._route_after_decision,
            {
                "delegate": "run_refactor",
                "skip": END,
            },
        )
        graph.add_edge("run_refactor", "run_verification")
        graph.add_edge("run_verification", END)

        return graph.compile()

    def _decide_delegation(self, state: AgentGraphState) -> AgentGraphState:
        decision = self._delegation_manager.decide(
            state["findings"],
            changed_files=state["changed_files"],
        )
        state["delegation_decision"] = decision
        if decision.should_delegate:
            state["handoff_log"].append(
                f"review_agent->refactoring_agent reasons={','.join(decision.reasons)}"
            )
        else:
            state["handoff_log"].append("review_agent decision=skip_delegation")
        return state

    def _run_refactor(self, state: AgentGraphState) -> AgentGraphState:
        updated_files, actions = self._refactoring_agent.apply(
            state["changed_files"],
            findings=state["findings"],
        )
        state["changed_files"] = updated_files
        state["refactor_actions"] = actions
        state["handoff_log"].append(f"refactoring_agent->verification_agent actions={len(actions)}")
        return state

    def _run_verification(self, state: AgentGraphState) -> AgentGraphState:
        result = self._verification_agent.verify(state["changed_files"])
        state["verification_result"] = result
        state["handoff_log"].append(f"verification_agent passed={result.passed}")
        return state

    def _route_after_decision(self, state: AgentGraphState) -> str:
        return "delegate" if state["delegation_decision"].should_delegate else "skip"
