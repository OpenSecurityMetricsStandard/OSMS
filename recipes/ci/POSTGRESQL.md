# Native PostgreSQL calculation-profile runner

Use a disposable PostgreSQL database. The runner creates temporary tables inside
transactions and rolls back every case. Connection parameters are the standard
`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` and `PGPASSWORD` environment variables;
passwords do not appear in command arguments or reports. `psql` must be available.

```sh
python recipes/gen_recipes.py --emit-candidates --out recipes/out
python recipes/ci/profile_runner.py --bundle recipes/out --engine postgresql
```

The report identifies the server version, exact profile bundle/source hashes,
card/output and each positive/negative case. A missing server or failed query
fails the requested run. DuckDB results do not count as PostgreSQL execution.
This profile checks canonical quotient inputs; it does not certify raw-source
adapters, all card families, installation settings or business data quality.
