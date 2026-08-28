// Demo 4 — the full Insightor answer shape: a user question answered with
// numbers, a chart, and a description that all come from the same verified facts.
//
// Simulated question: "أي المناطق سجلت أعلى نمو في المعاملات الرقمية خلال 2025؟"
// (Which regions grew the most in digital transactions during 2025?)
//
// In production: Vanna 2.0 produces the table, AVA verifies the patterns, and the
// LLM phrases the Arabic text FROM these computed numbers (never from memory).
import { render } from '@antv/gpt-vis-ssr';
import { getInsights } from '@antv/ava';
import { readCsv, savePng } from './lib.mjs';

const rows = readCsv('data/monthly_transactions.csv');

// --- numbers (what the SQL/analysis layer computes) -------------------------
const regions = [...new Set(rows.map((r) => r.region))];
const growth = regions.map((region) => {
  const series = rows.filter((r) => r.region === region);
  const first = series[0].transactions;
  const last = series[series.length - 1].transactions;
  return { region, first, last, growthPct: +(((last - first) / first) * 100).toFixed(1) };
}).sort((a, b) => b.growthPct - a.growthPct);

// --- verified highlights (AVA) ---------------------------------------------
const { insights } = getInsights(rows, {
  dimensions: [{ fieldName: 'month' }, { fieldName: 'region' }],
  measures: [{ fieldName: 'transactions', method: 'SUM' }],
  limit: 30,
});
const strongTrends = insights
  .flatMap((i) => (i.patterns ?? []).map((p) => ({ ...p, subspace: i.subspace })))
  .filter((p) => p.type === 'trend' && p.significance > 0.98);

// --- chart ------------------------------------------------------------------
const vis = await render({
  type: 'column',
  width: 800,
  height: 460,
  title: 'نمو المعاملات الرقمية خلال 2025 حسب المنطقة',
  axisXTitle: 'المنطقة',
  axisYTitle: 'نسبة النمو (%)',
  data: growth.map((g) => ({ category: g.region, value: g.growthPct })),
});
const chartFile = savePng('05-growth-by-region.png', vis.toBuffer());
vis.destroy();

// --- the answer bundle (what the user sees in chat) -------------------------
const [top, second] = growth;
const bundle = {
  headline: `${top.region} تتصدر بنمو ${top.growthPct}% خلال 2025`,
  answer:
    `سجلت ${top.region} أعلى نمو في المعاملات الرقمية خلال 2025 بنسبة ${top.growthPct}% ` +
    `(من ${top.first.toLocaleString('en')} معاملة في يناير إلى ${top.last.toLocaleString('en')} في ديسمبر)، ` +
    `تليها ${second.region} بنسبة ${second.growthPct}%. ` +
    `أدنى نمو كان في ${growth.at(-1).region} بنسبة ${growth.at(-1).growthPct}%.`,
  chart: chartFile,
  caption: 'نسبة النمو بين يناير وديسمبر 2025 لكل منطقة — مرتبة تنازلياً.',
  verified_facts: {
    growth_by_region: growth,
    significant_trends: strongTrends.map((t) => ({
      where: t.subspace?.map((s) => s.value).join(',') || 'all',
      significance: +t.significance.toFixed(3),
    })),
  },
};

console.log(JSON.stringify(bundle, null, 2));
