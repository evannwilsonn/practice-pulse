-- =====================================================================
-- Practice Pulse — warehouse layout
--
--   raw      data exactly as each system exports it: its own column
--            names, date formats and codes, stored as text. One table per
--            source file, named raw.<system>__<file>, e.g.
--              raw.pms_b__procedures, raw.sage_intacct__gl_detail
--   ref      seed / mapping tables (seeds/*.csv) that translate every
--            source code into shared categories
--   staging  typed, cleaned views; each source's codes translated and
--            every row tied to a master location_key
--   marts    business-ready tables the BI front end reads
--
-- Raw tables are created by build.py from the files the connectors land,
-- so their columns always match what the vendor actually sends.
-- Written for DuckDB; ports to Snowflake with minor type changes.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;
