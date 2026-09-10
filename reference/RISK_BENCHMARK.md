# Synthetic annual-loss benchmark

`risk-scenarios.json` fixes four synthetic profiles with 100,000 annual draws each:
zero events, independent scenarios, shared events and severities, and heavy tails.
`risk_scenarios.py` implements `compound-poisson/1` using NumPy 2.3.5 PCG64,
SeedSequence child streams in the declared scenario order, and seed 27004.
Event counts are Poisson. Severity is either the declared constant EUR amount or
Type I Pareto (`scale * (1 + Generator.pareto(shape))`). Losses sum within an
annual scenario and then within the same joint draw. Shared dependence copies
the complete first scenario draw and requires identical marginal parameters.
This benchmark deliberately does not claim a universal dependence model.

Inputs are residual losses; no second control multiplier is applied. STD-056's
ordinal criticality-gap result remains an index, not monetary residual loss.
The generator records its profile hash, actual Python/NumPy versions and a SHA-256
of little-endian float64 joint draws. Reproduction requires the pinned runtime,
profile and generator source. A seed alone is insufficient.

P50 is the arithmetic median; P90 uses nearest rank. Appetite exceedance is
strictly greater than the declared EUR amount. Frozen generated outputs are
regression references. Tests separately compare the constant-severity portfolios
with analytic Poisson exceedance probabilities (absolute sampling tolerance
0.002), check zero loss exactly, and verify changed dependence and a heavy tail.
Recorded deterministic numerical outputs use absolute tolerance 1e-8 EUR or
relative 1e-12, whichever is larger; counts are exact. These are different tests
from Monte Carlo uncertainty about a real organization's risk.

Run from the repository root:

```sh
python reference/risk_scenarios.py --out risk-benchmark-report.json
python -m unittest discover -s tests -p test_risk_scenarios.py
```

Fitting real event processes, loss distributions, scenario overlap and control
effectiveness requires model evidence. These synthetic scenarios are not pilot
observations or an organizational risk-appetite approval.
