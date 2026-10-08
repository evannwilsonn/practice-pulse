{# generic test: the model must return no rows #}
{% test empty(model) %}
select * from {{ model }}
{% endtest %}
