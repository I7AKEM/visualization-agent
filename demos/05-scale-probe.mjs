// Demo 5 — how does this stack behave when the CSV is big or wide?
// Measures: AVA insight timing, SSR render timing, and the size of the JSON a
// model would have to pass through an MCP tool call for raw (unaggregated) data.
import { render } from '@antv/gpt-vis-ssr';
import { getInsights } from '@antv/ava';
import { savePng } from './lib.mjs';

const months = Array.from({ length: 24 }, (_, i) =>
  `${2024 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}`);
const regions = ['الرياض','مكة المكرمة','الشرقية','عسير','المدينة المنورة','القصيم','تبوك','جازان'];
const services = Array.from({ length: 12 }, (_, i) => `خدمة ${i + 1}`);

function genRows(n) {
  const rows = [];
  for (let i = 0; i < n; i++) {
    rows.push({
      month: months[i % 24],
      region: regions[i % 8],
      service: services[i % 12],
      channel: i % 3 === 0 ? 'تطبيق' : i % 3 === 1 ? 'بوابة' : 'مكتب',
      value: Math.round(1000 + Math.random() * 9000 + (i % 24) * 120),
      fee: +(Math.random() * 50).toFixed(2),
      duration_min: Math.round(1 + Math.random() * 60),
      satisfied: Math.random() > 0.2 ? 1 : 0,
    });
  }
  return rows;
}

const t = async (label, fn) => {
  const s = performance.now();
  const out = await fn();
  console.log(`${label}: ${(performance.now() - s).toFixed(0)} ms`);
  return out;
};

for (const n of [1000, 5000, 20000]) {
  const rows = genRows(n);
  const json = JSON.stringify(rows);
  console.log(`\n--- ${n} rows × 8 columns | raw JSON ${(json.length/1024).toFixed(0)} KB ≈ ${Math.round(json.length/4/1000)}k tokens if passed through a tool call ---`);
  await t(`AVA getInsights (2 dims × 1 measure)`, () =>
    getInsights(rows, {
      dimensions: [{ fieldName: 'month' }, { fieldName: 'region' }],
      measures: [{ fieldName: 'value', method: 'SUM' }],
      limit: 5,
    }));
}

// dense single-series line: 5,000 points
const line = Array.from({ length: 5000 }, (_, i) => ({
  time: String(i), value: Math.sin(i / 80) * 50 + 100 + Math.random() * 10 }));
const v1 = await t('SSR render line with 5,000 points', () =>
  render({ type: 'line', data: line, title: 'اختبار ٥٠٠٠ نقطة', width: 900, height: 400 }));
savePng('06-stress-line-5000pts.png', v1.toBuffer()); v1.destroy();

// 300 categories in one column chart
const cats = Array.from({ length: 300 }, (_, i) => ({ category: `جهة ${i + 1}`, value: Math.round(Math.random() * 1000) }));
const v2 = await t('SSR render column with 300 categories', () =>
  render({ type: 'column', data: cats, title: 'اختبار ٣٠٠ فئة', width: 900, height: 400 }));
savePng('07-stress-column-300cats.png', v2.toBuffer()); v2.destroy();

console.log('\nscale probe done');
