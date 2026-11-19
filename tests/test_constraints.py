from timetravel.constraints import ConstraintKind, ConstraintViolation


def test_violation_records_responsible_events():
    violation = ConstraintViolation("existence", ("a", "b"), "Conflicting assertions")
    assert violation.event_ids == ("a", "b")
    assert violation.kind == ConstraintKind.LOGICAL


def test_causal_violation_can_carry_directed_relation_evidence():
    violation = ConstraintViolation("precedence", ("a", "b"), "Missing dependency",
                                    ConstraintKind.CAUSAL, (("a", "b"),))
    assert violation.relations == (("a", "b"),)
