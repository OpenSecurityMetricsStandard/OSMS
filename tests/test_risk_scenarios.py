# SPDX-License-Identifier: MIT
import copy,json,math,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from risk_scenarios import generate

class RiskScenariosTests(unittest.TestCase):
    def test_frozen_zero_dependence_and_heavy_tail_benchmarks(self):
        profiles=json.loads((ROOT/'reference/risk-scenarios.json').read_text())['profiles']
        results={p['profile_id']:generate(p) for p in profiles}
        zero=results['zero']['outputs'];self.assertEqual(zero['mean'],0);self.assertEqual(zero['zero_event_draws'],100000)
        self.assertGreater(results['correlated']['outputs']['probability_exceeding_appetite'],results['independent']['outputs']['probability_exceeding_appetite'])
        # Separate analytic Poisson oracles, not generated expected values.
        for key,rate,limit in [('independent',2,5),('correlated',1,2)]:
            expected=1-math.exp(-rate)*sum(rate**k/math.factorial(k) for k in range(limit+1))
            self.assertAlmostEqual(results[key]['outputs']['probability_exceeding_appetite'],expected,delta=.002)
        self.assertGreater(results['heavy_tail']['outputs']['maximum'],100*results['heavy_tail']['outputs']['p90'])
        for p in profiles:
            self.assertEqual(results[p['profile_id']],generate(p))
            expected=p['expected']
            for k,v in expected.items():self.assertAlmostEqual(results[p['profile_id']]['outputs'][k],v,delta=max(1e-8,abs(v)*1e-12))

    def test_invalid_model_or_control_credit_cannot_be_silently_accepted(self):
        p=json.loads((ROOT/'reference/risk-scenarios.json').read_text())['profiles'][0]
        for k,v in [('numpy_version','unknown'),('iterations',99999),('seed',True),('dependence','unspecified'),('control_credit_policy','apply_controls_twice')]:
            bad=copy.deepcopy(p);bad[k]=v
            with self.assertRaises(ValueError):generate(bad)

if __name__=='__main__':unittest.main()
