// OSMS KQL analyzer batch - validates every generated KQL snippet
// usage: node recipes/kql_check.js <path-to-kql_jobs.json>
global.window = global; global.self = global;
require("@kusto/language-service-next/bridge.min.js");
require("@kusto/language-service-next/Kusto.Language.Bridge.min.js");
const K = Kusto.Language;
const jobs = require(require("path").resolve(process.argv[2]));
let fail = 0;
for (const j of jobs) {
  const d = K.KustoCode.ParseAndAnalyze(j.q).GetDiagnostics();
  if (d.Count > 0) { fail++; if (fail <= 5) {
    const m = []; for (let i = 0; i < Math.min(d.Count, 2); i++) m.push(d.getItem(i).Message);
    console.log("FAIL", j.id, JSON.stringify(m)); } }
}
console.log(`kql_check: ${jobs.length - fail}/${jobs.length} PASS`);
process.exit(fail ? 1 : 0);
