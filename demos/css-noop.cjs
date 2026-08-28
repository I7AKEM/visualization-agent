// @antv/s2 (pulled in via gpt-vis-ssr -> s2-ssr) requires .css files from its CJS
// build, which plain Node cannot parse. Preload with `node -r ./demos/css-noop.cjs`
// to treat .css requires as empty modules.
require.extensions['.css'] = () => {};
