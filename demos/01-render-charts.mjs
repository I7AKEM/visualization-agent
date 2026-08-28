// Demo 1 — render charts server-side from CSV (the output of Insightor's SQL tool)
// using @antv/gpt-vis-ssr, with Arabic titles, axis titles, and category labels.
import { render } from '@antv/gpt-vis-ssr';
import { readCsv, savePng, sumBy } from './lib.mjs';

const rows = readCsv('data/monthly_transactions.csv');
const services = readCsv('data/service_breakdown.csv');

const specs = [
  {
    name: '01-line-by-region.png',
    options: {
      type: 'line',
      width: 900,
      height: 500,
      title: 'المعاملات الرقمية الشهرية حسب المنطقة — 2025',
      axisXTitle: 'الشهر',
      axisYTitle: 'عدد المعاملات',
      data: rows.map((r) => ({ time: r.month, value: r.transactions, group: r.region })),
    },
  },
  {
    name: '02-column-totals.png',
    options: {
      type: 'column',
      width: 800,
      height: 480,
      title: 'إجمالي المعاملات لعام 2025 حسب المنطقة',
      axisXTitle: 'المنطقة',
      axisYTitle: 'إجمالي المعاملات',
      data: sumBy(rows, 'region', 'transactions')
        .sort((a, b) => b.transactions - a.transactions)
        .map((r) => ({ category: r.region, value: r.transactions })),
    },
  },
  {
    name: '03-pie-services.png',
    options: {
      type: 'pie',
      width: 700,
      height: 500,
      title: 'توزيع المعاملات حسب نوع الخدمة',
      innerRadius: 0.6,
      data: services.map((r) => ({ category: r.service, value: r.transactions })),
    },
  },
  {
    name: '04-bar-dark-theme.png',
    options: {
      type: 'bar',
      width: 800,
      height: 480,
      theme: 'dark',
      title: 'إجمالي المعاملات حسب المنطقة (سمة داكنة)',
      axisXTitle: 'إجمالي المعاملات',
      axisYTitle: 'المنطقة',
      data: sumBy(rows, 'region', 'transactions')
        .sort((a, b) => b.transactions - a.transactions)
        .map((r) => ({ category: r.region, value: r.transactions })),
    },
  },
];

for (const { name, options } of specs) {
  const vis = await render(options);
  savePng(name, vis.toBuffer());
  vis.destroy();
}
console.log('demo 1 done');
