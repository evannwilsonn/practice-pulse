{# Small helpers so the same models run on BigQuery (production) and Postgres (local test). #}

{# money / measures #}
{% macro num(expr) -%} cast({{ expr }} as {{ dbt.type_numeric() }}) {%- endmacro %}
{% macro int(expr) -%} cast({{ expr }} as {{ dbt.type_int() }}) {%- endmacro %}

{# first day of the month, as a DATE #}
{% macro month_of(expr) -%} cast({{ dbt.date_trunc('month', expr) }} as date) {%- endmacro %}

{# parse a text date using strftime-style codes: %Y %m %d %b #}
{% macro parse_date(expr, fmt) -%}
  {{ return(adapter.dispatch('parse_date', 'practice_pulse')(expr, fmt)) }}
{%- endmacro %}
{% macro bigquery__parse_date(expr, fmt) -%} parse_date('{{ fmt }}', {{ expr }}) {%- endmacro %}
{% macro default__parse_date(expr, fmt) -%}
  to_date({{ expr }}, '{{ fmt | replace("%Y", "YYYY") | replace("%m", "MM") | replace("%d", "DD") | replace("%b", "Mon") }}')
{%- endmacro %}

{# text column type for seeds #}
{% macro text_type() -%} {{ 'string' if target.type == 'bigquery' else 'text' }} {%- endmacro %}
