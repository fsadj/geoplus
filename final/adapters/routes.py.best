from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteSpec:
    name: str
    source_index: int
    step2_instruction: str
    citation_instruction: str
    enabled_by_default: bool = True


ROUTE_SPECS = [
    RouteSpec(
        name="after_primary_spine",
        source_index=1,
        step2_instruction="只围绕前三问沉淀一条最稳的主结论、责任链和制度依据。优先保留最容易被直接摘取的判断句、责任句、制度句和必要边界，不追求全面综述。",
        citation_instruction="把 5.2 中最稳的一条主线收束成可直接充当最终主稿的引用稿。只保留 3 到 4 组最强依据，持续重复同一套主术语和主结论。",
    ),
    RouteSpec(
        name="after_boundary_cases",
        source_index=3,
        step2_instruction="专门补主线最容易缺失的高价值边界、反驳、责任防火墙和典型案例，但所有补充都必须直接服务前三问，不能自成大综述。",
        citation_instruction="把 5.2 中最值钱的边界、反驳和案例压成一篇补强型引用稿。它仍然要直接回答问题，但只能围绕主结论补强，不得发展成第二条竞争主线。",
    ),
    RouteSpec(
        name="after_extra_coverage_floor",
        source_index=2,
        step2_instruction="完全沿用旧 coverage_floor 的核心思路：先保目标文档核心判断，再补一组最小共享覆盖。共享覆盖只能选那些多份材料都支持、且最能影响回答命中的共识信息；不能回退成大段背景综述，也不能挤掉差异化判断。每段首句尽量可单独引用。",
        citation_instruction="继续沿用 coverage_floor 模式收束 5.2：先直接回答问题，再围绕关键依据、条件边界和最终判断组织内容；在保留主稿核心判断的前提下，只补最小必要的共同覆盖，避免机械罗列共识或展开第二条主线。每段首句尽量可单独引用。",
        enabled_by_default=True,
    ),
]


def list_routes() -> list[RouteSpec]:
    return [route for route in ROUTE_SPECS if route.enabled_by_default]


def get_extra_route() -> RouteSpec:
    for route in ROUTE_SPECS:
        if route.name == "after_extra_coverage_floor":
            return route
    raise KeyError("extra coverage_floor route is missing")


def get_route(name: str) -> RouteSpec:
    for route in ROUTE_SPECS:
        if route.name == name:
            return route
    raise KeyError(f"unknown route: {name}")
