def root_cause_evaluator(outputs, reference_outputs):
    e = reference_outputs.get("expected_root_cause", "")
    a = outputs.get("root_cause", "")
    return {
        "key": "root_cause_correct",
        "score": float(a == e),
        "comment": f"expected={e!r}, actual={a!r}",
    }


def resolved_evaluator(outputs, reference_outputs):
    e = bool(reference_outputs.get("expected_resolved_after_approval"))
    a = bool(outputs.get("resolved"))
    return {
        "key": "resolved_correct",
        "score": float(a == e),
        "comment": f"expected={e}, actual={a}",
    }
