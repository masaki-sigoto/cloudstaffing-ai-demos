"""ルール共通の Finding 生成ヘルパー。"""

from __future__ import annotations

from ...models import Finding, Scope


def make_finding_record(p, case, pattern_id: str, pattern_name: str, raw_context=None) -> Finding:
    return Finding(
        pattern_id=pattern_id,
        pattern_name=pattern_name,
        scope=Scope.RECORD,
        record_id=p.record_id,
        day_key=case.day_key,
        staff_id=p.staff_id,
        staff_name=p.staff_name,
        date=p.date,
        client_id=p.client_id,
        client_name=p.client_name,
        client_site=p.client_site,
        assignee_id=p.assignee_id,
        assignee_name=p.assignee_name,
        approver_statuses=tuple(case.approver_statuses),
        raw_context=raw_context or {},
    )


def make_finding_day(case, pattern_id: str, pattern_name: str, raw_context=None) -> Finding:
    # case 代表の名前（punches があれば先頭を流用、無ければ空）
    if case.punches:
        sn = case.punches[0].staff_name
        cname = case.punches[0].client_name
        aname = case.punches[0].assignee_name
    else:
        sn = ""
        cname = case.client_id or ""
        aname = ""
    return Finding(
        pattern_id=pattern_id,
        pattern_name=pattern_name,
        scope=Scope.DAY,
        record_id=None,
        day_key=case.day_key,
        staff_id=case.staff_id,
        staff_name=sn,
        date=case.date,
        client_id=case.client_id,
        client_name=cname,
        client_site=case.client_site,
        assignee_id=case.assignee_id,
        assignee_name=aname,
        approver_statuses=tuple(case.approver_statuses),
        raw_context=raw_context or {},
    )


def make_finding_application(case, app, pattern_id: str, pattern_name: str, raw_context=None) -> Finding:
    if case.punches:
        sn = case.punches[0].staff_name
        cname = case.punches[0].client_name
        aname = case.punches[0].assignee_name
    else:
        sn = ""
        cname = case.client_id or ""
        aname = ""
    return Finding(
        pattern_id=pattern_id,
        pattern_name=pattern_name,
        scope=Scope.APPLICATION,
        record_id=None,
        application_id=app.application_id,
        day_key=case.day_key,
        staff_id=case.staff_id,
        staff_name=sn,
        date=case.date,
        client_id=case.client_id,
        client_name=cname,
        client_site=case.client_site,
        assignee_id=case.assignee_id,
        assignee_name=aname,
        approver_statuses=tuple(case.approver_statuses),
        raw_context=raw_context or {},
    )
