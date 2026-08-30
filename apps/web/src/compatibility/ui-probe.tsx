import { Bubble } from "@ant-design/x";
import { Button, ConfigProvider } from "antd";

export function UiCompatibilityProbe() {
  return (
    <ConfigProvider>
      <section aria-label="UI compatibility probe">
        <Bubble content="Hydration probe" />
        <Button type="primary">Compatibility</Button>
      </section>
    </ConfigProvider>
  );
}
