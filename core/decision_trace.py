

from __future__ import annotations


def check(label, passed=None, detail=None):
    state = "info" if passed is None else ("pass" if passed else "fail")
    result = {"label": str(label), "state": state}
    if detail:
        result["detail"] = str(detail)
    return result


def fact(label, value):
    return {"label": str(label), "value": str(value)}


def make(status, reason_code, module, summary, *, checks=None, facts=None,
         next_step=None):
    trace = {
        "status": str(status),
        "reasonCode": str(reason_code),
        "module": str(module),
        "summary": str(summary),
        "checks": list(checks or []),
        "facts": list(facts or []),
    }
    if next_step:
        trace["nextStep"] = dict(next_step)
    return trace
