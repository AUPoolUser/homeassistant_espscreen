# ESPHome `ethernet`, with a CH390 chip select on an IO expander

This is ESPHome 2026.9.1's own `ethernet` component with one addition, for the Portworld YC-SM43P wall panel.
Its CH390D Ethernet chip has its chip select (SCS) and reset (RSTB) on an NCA9555 (TCA9555) IO expander, not
on ESP32-S3 pins, and ESPHome's `ethernet:` only accepts chip pins for those.

Two options are added for `type: CH390` on ESP32:

- `expander_cs_pin`: the chip select, as any ESPHome pin (an expander pin included). Use it instead of `cs_pin`.
- `expander_reset_pin`: the reset, as any ESPHome pin. The chip is held in reset for 10 ms at start-up.

With `expander_cs_pin`, the CH390 is added to the SPI host without a hardware chip select, and a custom SPI driver
(`ch390_expander_spi.cpp`, after ESPHome's own `w5500_custom_spi.cpp`) asserts and releases the pin around every
transfer, as Portworld's firmware does. Every edge is an I2C write, so throughput is a fraction of a native chip
select, but ample for Home Assistant's API. Without those options the component behaves exactly as ESPHome's.

Tried on a YC-SM43P on 2026-10-16 (ESPHome 2026.9.1, Tessera firmware 0.56.0, powered by 802.3af PoE): the
CH390D took a DHCP address on the wire next to Wi-Fi, and answered ping with no loss at 6 to 13 ms.

It shadows ESPHome's built-in component, so it must match the ESPHome version that builds it (2026.9.x).

```yaml
external_components:
  - source:
      type: git
      url: https://github.com/AUPoolUser/homeassistant_espscreen
      ref: yc-sm43p-ethernet
      path: components
    components: [ethernet]

network:
  priority: [ethernet, wifi]   # Ethernet first, Wi-Fi as the fallback

ethernet:
  type: CH390
  clk_pin: GPIO42
  mosi_pin: GPIO2
  miso_pin: GPIO1
  interrupt_pin: GPIO6
  clock_speed: 20MHz
  expander_cs_pin:
    tca9555: expander
    number: 5
  expander_reset_pin:
    tca9555: expander
    number: 7
```

Changed files against ESPHome 2026.9.1: `__init__.py`, `ethernet_component.h`, `ethernet_component_esp32.cpp`;
added: `ch390_expander_spi.h`, `ch390_expander_spi.cpp`, this file.
