{# Use the schema names as written (ref, staging, marts) instead of dbt's default public_ref etc. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
