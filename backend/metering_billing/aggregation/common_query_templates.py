CAGG_REFRESH = """
SELECT add_continuous_aggregate_policy('{{ cagg_name }}',
    start_offset => INTERVAL '32 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);
"""

CAGG_DROP = """
DROP MATERIALIZED VIEW IF EXISTS {{ cagg_name }};
"""

CAGG_COMPRESSION = """
ALTER MATERIALIZED VIEW {{ cagg_name }} set (timescaledb.compress = true);
SELECT add_compression_policy(
    '{{ cagg_name }}',
    compress_after=>'33 days'::interval,
    if_not_exists=>true
);
"""
