from timetravel.constraints import ConstraintViolation


def test_violation_records_responsible_events():
    violation = ConstraintViolation("existence", ("a", "b"), "Conflicting assertions")
    assert violation.event_ids == ("a", "b")
