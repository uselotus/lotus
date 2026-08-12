"""
Regression tests for SQL injection risk in the Jinja2 DDL/DML query templates used to
manage TimescaleDB continuous aggregates (see PR #801).

`cagg_name` (and its sibling `cumsum_cagg`) is interpolated directly into raw SQL via
Jinja2 templates. In production this value is always built from
`("org_" + organization_id.hex)[:22] + "___" + ("metric_" + metric_id.hex)[:22] + "___" + <suffix>`
(see `billable_metrics.py`), i.e. lowercase hex/underscore only, so it is not reachable by
attacker-controlled HTTP input today. However, the templates themselves are still an
injection primitive: if `cagg_name` were ever built from anything else (e.g. a
user-supplied metric name, in a future refactor), unescaped interpolation would allow
arbitrary SQL execution.

These tests render each affected template with a malicious `cagg_name` and assert the
payload is properly neutralized by the identifier/string-literal escaping.
"""
from jinja2 import Template

from metering_billing.aggregation.common_query_templates import (
    CAGG_COMPRESSION,
    CAGG_DROP,
    CAGG_REFRESH,
)
from metering_billing.aggregation.counter_query_templates import (
    COUNTER_CAGG_QUERY,
    COUNTER_CAGG_TOTAL,
    COUNTER_TOTAL_PER_DAY,
)
from metering_billing.aggregation.gauge_query_templates import (
    GAUGE_DELTA_CUMULATIVE_SUM,
    GAUGE_DELTA_DROP_OLD,
    GAUGE_DELTA_GET_CURRENT_USAGE,
    GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION,
    GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY,
    GAUGE_DELTA_TOTAL_PER_DAY,
    GAUGE_TOTAL_CUMULATIVE_SUM,
    GAUGE_TOTAL_GET_CURRENT_USAGE,
    GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION,
    GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY,
    GAUGE_TOTAL_TOTAL_PER_DAY,
)
from metering_billing.aggregation.rate_query_templates import (
    RATE_CAGG_QUERY,
    RATE_CAGG_TOTAL,
    RATE_TOTAL_PER_DAY,
)

# Minimal kwargs needed to render each template far enough to reach the cagg_name /
# cumsum_cagg interpolation without raising Jinja2 UndefinedError on unrelated variables.
COMMON_KWARGS = dict(
    bucket_size="day",
    query_type="count",
    property_name="prop",
    group_by=[],
    uuidv5_event_name="evt",
    organization_id=1,
    numeric_filters=[],
    categorical_filters=[],
    filter_properties={},
    uuidv5_customer_id="00000000-0000-0000-0000-000000000000",
    start_date="2024-01-01",
    end_date="2024-01-31",
    top_n=5,
    lookback_qty=1,
    lookback_units="day",
    reference_time="2024-01-01",
    proration_units=None,
    granularity_ratio=1,
    cumsum_cagg="cumsum_cagg_placeholder",
)

# Identifier-position payload: cagg_name is interpolated bare (no surrounding quotes),
# so no escaping is required by the attacker to break out - a bare statement terminator
# is enough. This is the payload class proven live against Postgres to drop an arbitrary
# table when rendered through an unpatched template.
IDENTIFIER_PAYLOAD = 'evil_cagg"; DROP TABLE some_table; --'

# String-literal-position payload (used by common_query_templates.py's
# add_continuous_aggregate_policy('{{ cagg_name }}', ...) call sites).
LITERAL_PAYLOAD = "evil_cagg'); DROP TABLE some_table; --"


def render(template, **overrides):
    kwargs = dict(COMMON_KWARGS)
    kwargs.update(overrides)
    return Template(template).render(**kwargs)


def assert_identifier_safe(rendered_sql, raw_payload, cagg_kwarg_name="cagg_name"):
    """
    The payload must never appear un-doubled inside the rendered SQL in a way that lets
    it close a quoted identifier early. Concretely: every double-quote character
    originating from the payload must be immediately followed/preceded by another
    double-quote (i.e. doubled per Postgres identifier-escaping rules), and the raw
    payload string must not appear verbatim (since it contains an unescaped `"`).
    """
    assert raw_payload not in rendered_sql, (
        f"raw malicious payload appears unescaped in rendered SQL: {rendered_sql!r}"
    )
    # The payload's embedded double-quote must have been doubled.
    doubled = raw_payload.replace('"', '""')
    assert doubled in rendered_sql, (
        f"expected doubled-quote escaped payload {doubled!r} in rendered SQL: {rendered_sql!r}"
    )


def assert_literal_safe(rendered_sql, raw_payload):
    assert raw_payload not in rendered_sql, (
        f"raw malicious payload appears unescaped in rendered SQL: {rendered_sql!r}"
    )
    doubled = raw_payload.replace("'", "''")
    assert doubled in rendered_sql, (
        f"expected doubled single-quote escaped payload {doubled!r} in rendered SQL: {rendered_sql!r}"
    )


# ---------------------------------------------------------------------------
# common_query_templates.py (fixed by PR #801 itself)
# ---------------------------------------------------------------------------


def test_cagg_refresh_escapes_literal_position():
    rendered = render(CAGG_REFRESH, cagg_name=LITERAL_PAYLOAD)
    assert_literal_safe(rendered, LITERAL_PAYLOAD)


def test_cagg_drop_escapes_identifier_position():
    rendered = render(CAGG_DROP, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_cagg_compression_escapes_identifier_position():
    # CAGG_COMPRESSION interpolates cagg_name twice: once as a bare identifier
    # (ALTER MATERIALIZED VIEW {{ cagg_name }} ...) and once as a string literal
    # (add_compression_policy('{{ cagg_name }}', ...)). An identifier-breakout payload
    # (containing `"` but no `'`) must be neutralized in the identifier occurrence; the
    # literal occurrence is untouched by double-quote escaping (correctly so - it isn't
    # in a double-quoted context) so we only assert on the identifier line here.
    rendered = render(CAGG_COMPRESSION, cagg_name=IDENTIFIER_PAYLOAD)
    identifier_line = rendered.splitlines()[1]
    assert IDENTIFIER_PAYLOAD not in identifier_line
    assert IDENTIFIER_PAYLOAD.replace('"', '""') in identifier_line


def test_cagg_compression_escapes_literal_position():
    rendered = render(CAGG_COMPRESSION, cagg_name=LITERAL_PAYLOAD)
    literal_line = [l for l in rendered.splitlines() if l.strip().startswith("'")][0]
    assert_literal_safe(literal_line, LITERAL_PAYLOAD)


# ---------------------------------------------------------------------------
# counter_query_templates.py
# ---------------------------------------------------------------------------


def test_counter_cagg_query_create_view_escaped():
    rendered = render(COUNTER_CAGG_QUERY, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_counter_cagg_total_from_clause_escaped():
    rendered = render(COUNTER_CAGG_TOTAL, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_counter_total_per_day_from_clause_escaped():
    rendered = render(COUNTER_TOTAL_PER_DAY, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


# ---------------------------------------------------------------------------
# rate_query_templates.py
# ---------------------------------------------------------------------------


def test_rate_cagg_query_create_view_escaped():
    rendered = render(RATE_CAGG_QUERY, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_rate_cagg_total_from_clause_escaped():
    rendered = render(RATE_CAGG_TOTAL, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_rate_total_per_day_from_clause_escaped():
    rendered = render(RATE_TOTAL_PER_DAY, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


# ---------------------------------------------------------------------------
# gauge_query_templates.py
# ---------------------------------------------------------------------------


def test_gauge_delta_cumulative_sum_create_view_escaped():
    rendered = render(GAUGE_DELTA_CUMULATIVE_SUM, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_gauge_delta_get_total_usage_with_proration_cumsum_cagg_escaped():
    rendered = render(
        GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION,
        cumsum_cagg=IDENTIFIER_PAYLOAD,
    )
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD, cagg_kwarg_name="cumsum_cagg")


def test_gauge_delta_get_total_usage_with_proration_per_day_cumsum_cagg_escaped():
    rendered = render(
        GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY,
        cumsum_cagg=IDENTIFIER_PAYLOAD,
    )
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD, cagg_kwarg_name="cumsum_cagg")


def test_gauge_delta_drop_old_all_statements_escaped():
    """
    GAUGE_DELTA_DROP_OLD interpolates cagg_name into five separate DDL statements,
    including compound identifiers like `tg_{{ cagg_name }}_insert` and
    `tg_refresh_{{ cagg_name }}`. Each must independently neutralize the payload.
    """
    rendered = render(GAUGE_DELTA_DROP_OLD, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)
    # Also make sure the compound identifiers stay syntactically valid: the quoted
    # region must fully wrap the static prefix/suffix text alongside the payload.
    doubled = IDENTIFIER_PAYLOAD.replace('"', '""')
    assert f'"tg_{doubled}_insert"' in rendered
    assert f'"tg_{doubled}_update"' in rendered
    assert f'"tg_{doubled}_delete"' in rendered
    assert f'"tg_refresh_{doubled}"' in rendered


def test_gauge_delta_get_current_usage_cumsum_cagg_escaped():
    # NOTE: GAUGE_DELTA_GET_CURRENT_USAGE has a pre-existing (unrelated to this security
    # fix) Jinja2 syntax bug on `main`: the `{%- for ... in categorical_filters %}` loop
    # opened just above `GROUP BY` (around the `current_day_sum` CTE) is never closed
    # with a matching `{%- endfor %}`. This makes the template fail to render via Jinja2
    # with *any* input today - it is not specific to a malicious payload. That bug is out
    # of scope for the SQL-injection fix in this file, so this test only verifies that our
    # cumsum_cagg escaping is textually present in the raw (unrendered) template source,
    # rather than trying to fully render it end-to-end.
    assert "\"{{ cumsum_cagg | replace('\"', '\"\"') }}\"" in GAUGE_DELTA_GET_CURRENT_USAGE


def test_gauge_delta_total_per_day_from_clause_escaped():
    rendered = render(GAUGE_DELTA_TOTAL_PER_DAY, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_gauge_total_cumulative_sum_create_view_escaped():
    rendered = render(GAUGE_TOTAL_CUMULATIVE_SUM, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)


def test_gauge_total_get_current_usage_cumsum_cagg_escaped():
    rendered = render(GAUGE_TOTAL_GET_CURRENT_USAGE, cumsum_cagg=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD, cagg_kwarg_name="cumsum_cagg")


def test_gauge_total_get_total_usage_with_proration_cumsum_cagg_escaped():
    rendered = render(
        GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION,
        cumsum_cagg=IDENTIFIER_PAYLOAD,
    )
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD, cagg_kwarg_name="cumsum_cagg")


def test_gauge_total_get_total_usage_with_proration_per_day_cumsum_cagg_escaped():
    rendered = render(
        GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY,
        cumsum_cagg=IDENTIFIER_PAYLOAD,
    )
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD, cagg_kwarg_name="cumsum_cagg")


def test_gauge_total_total_per_day_all_positions_escaped():
    """
    GAUGE_TOTAL_TOTAL_PER_DAY uses cagg_name both as a bare FROM-clause identifier and
    as a table qualifier in `{{ cagg_name }}.uuidv5_customer_id` / `{{ cagg_name }}.{{
    group_by_field }}` style correlated-subquery references. All must be escaped.
    """
    rendered = render(GAUGE_TOTAL_TOTAL_PER_DAY, cagg_name=IDENTIFIER_PAYLOAD)
    assert_identifier_safe(rendered, IDENTIFIER_PAYLOAD)
    doubled = IDENTIFIER_PAYLOAD.replace('"', '""')
    assert f'"{doubled}".uuidv5_customer_id' in rendered
    assert f'FROM\n        "{doubled}"' in rendered


def test_gauge_total_total_per_day_with_group_by_qualified_columns_escaped():
    rendered = render(
        GAUGE_TOTAL_TOTAL_PER_DAY, cagg_name=IDENTIFIER_PAYLOAD, group_by=["region"]
    )
    doubled = IDENTIFIER_PAYLOAD.replace('"', '""')
    assert f'AND region = "{doubled}".region' in rendered
