// Demo 2 — AVA: automatic insight extraction + chart recommendation on the SQL output.
// This is the "what should the executive be told?" layer: it finds trends, outliers
// and seasonality in plain data, with a significance score for each.
import { getInsights, Advisor } from '@antv/ava';
import { readCsv, sumBy } from './lib.mjs';

const rows = readCsv('data/monthly_transactions.csv');

// --- 1. Automatic insights -------------------------------------------------
const { insights, homogeneousInsights } = getInsights(rows, {
  dimensions: [{ fieldName: 'month' }, { fieldName: 'region' }],
  measures: [{ fieldName: 'transactions', method: 'SUM' }],
  limit: 10,
  homogeneous: true,
  visualization: { lang: 'en-US' },
});

console.log(`\n=== ${insights.length} insights found ===`);
for (const ins of insights) {
  const subspace = ins.subspace?.map((s) => `${s.dimension}=${s.value}`).join(', ') || 'all data';
  for (const p of ins.patterns ?? []) {
    const where = p.x !== undefined ? ` @ ${p.x}` : '';
    console.log(
      `- [${p.type}] (${subspace})${where}  significance=${p.significance?.toFixed(3)}`
    );
  }
  const narrative = ins.visualizationSpecs?.[0]?.narrativeSpec;
  if (narrative) console.log(`  narrative: ${JSON.stringify(narrative)}`);
}

if (homogeneousInsights?.length) {
  console.log(`\n=== ${homogeneousInsights.length} homogeneous (cross-group) insights ===`);
  for (const h of homogeneousInsights) {
    console.log(`- ${h.patterns?.[0]?.type ?? '?'} shared across groups, significance=${h.patterns?.[0]?.significance}`);
  }
}

// --- 2. Chart recommendation (Advisor) -------------------------------------
const totals = sumBy(rows, 'region', 'transactions');
const advisor = new Advisor();
const advices = advisor.advise({ data: totals });
console.log('\n=== chart advisor: best chart for region totals ===');
for (const a of advices.slice(0, 4)) console.log(`- ${a.type} (score ${a.score.toFixed(2)})`);

const timeSeries = rows.filter((r) => r.region === 'الرياض').map(({ month, transactions }) => ({ month, transactions }));
const advices2 = advisor.advise({ data: timeSeries });
console.log('\n=== chart advisor: best chart for a monthly series ===');
for (const a of advices2.slice(0, 4)) console.log(`- ${a.type} (score ${a.score.toFixed(2)})`);
console.log('\ndemo 2 done');
