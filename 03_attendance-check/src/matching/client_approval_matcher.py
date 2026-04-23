"""staff × date × client × site × assignee で合流し MatchedCase を生成。"""

from __future__ import annotations

from collections import defaultdict

from ..models import MatchedCase


class ClientApprovalMatcher:
    def __init__(self, skip_reporter) -> None:
        self.skip_reporter = skip_reporter

    def match(self, punches: list, leaves_all: list, shifts: list) -> list:
        # punches: 5キーでグループ化
        grouped: dict = defaultdict(list)
        for p in punches:
            key = (p.staff_id, p.date, p.client_id, p.client_site, p.assignee_id)
            grouped[key].append(p)

        # shifts: staff × date で辞書化
        shift_map: dict = {}
        for s in shifts:
            shift_map[(s.staff_id, s.date)] = s

        # leaves/overtimes を staff × date で bucket 化
        leave_map: dict = defaultdict(list)
        overtime_map: dict = defaultdict(list)
        for a in leaves_all:
            if a.type == "leave":
                leave_map[(a.staff_id, a.date)].append(a)
            elif a.type == "overtime":
                overtime_map[(a.staff_id, a.date)].append(a)

        cases: list = []
        seen_virtual_keys: set = set()

        # punches のある case
        for (sid, d, cid, site, aid), ps in grouped.items():
            leaves_here = list(leave_map.get((sid, d), []))
            overtimes_here = list(overtime_map.get((sid, d), []))
            shift_here = shift_map.get((sid, d))
            statuses = [a.status for a in leaves_here + overtimes_here]
            cases.append(
                MatchedCase(
                    staff_id=sid,
                    date=d,
                    client_id=cid,
                    client_site=site,
                    assignee_id=aid,
                    punches=ps,
                    leaves=leaves_here,
                    overtimes=overtimes_here,
                    shift=shift_here,
                    approver_statuses=statuses,
                )
            )

        # punches が無く leaves/overtimes のみ: 仮想 case を立てる
        all_punch_sdate = {(p.staff_id, p.date) for p in punches}
        for (sid, d), leaves_here in leave_map.items():
            if (sid, d) in all_punch_sdate:
                continue
            if (sid, d) in seen_virtual_keys:
                continue
            seen_virtual_keys.add((sid, d))
            overtimes_here = list(overtime_map.get((sid, d), []))
            statuses = [a.status for a in leaves_here + overtimes_here]
            cases.append(
                MatchedCase(
                    staff_id=sid,
                    date=d,
                    client_id="",
                    client_site="unknown",
                    assignee_id="",
                    punches=[],
                    leaves=leaves_here,
                    overtimes=overtimes_here,
                    shift=shift_map.get((sid, d)),
                    approver_statuses=statuses,
                )
            )
        for (sid, d), overtimes_here in overtime_map.items():
            if (sid, d) in all_punch_sdate:
                continue
            if (sid, d) in seen_virtual_keys:
                continue
            seen_virtual_keys.add((sid, d))
            statuses = [a.status for a in overtimes_here]
            cases.append(
                MatchedCase(
                    staff_id=sid,
                    date=d,
                    client_id="",
                    client_site="unknown",
                    assignee_id="",
                    punches=[],
                    leaves=[],
                    overtimes=overtimes_here,
                    shift=shift_map.get((sid, d)),
                    approver_statuses=statuses,
                )
            )
        return cases
