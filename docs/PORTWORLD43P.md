# Portworld YC-SM43P, experimental

This is the **Portworld YC-SM43P** (sold as the "YC-SM43P ESP32 4″ Smart Touch Panel"): a 4-inch 480 x 480 IPS panel
with an ST7701S driver over RGB, GT911 capacitive touch, an ESP32-S3 (N16R8: 16 MB flash, 8 MB octal PSRAM) in an
86 x 86 wall box, with a CH390D Ethernet chip, RS485, an optional AHT20 temperature and humidity sensor and a buzzer.
It is powered by 802.3af PoE (48 V), 12 V DC or USB-C.

Tried on one unit on 2026-10-15 with ESPHome 2026.9.1, using this board's pins and timings in a plain ESPHome
configuration: the ESPHome test card drew with its colours in order, unmirrored and edge to edge after a cold start;
the GT911 answered at 0x5D and read 3 to 474 on both axes with the centre at about 218 x 234; the I2C scan found the
expander (0x20), the AHT20 (0x38, reading 27.0 °C and 31.8 %RH inside the case), the real-time clock (0x51) and the
GT911. The Tessera firmware itself has not been on the glass yet. ESPHome reports the pixel clock as 20 MHz.

## Install

Choose **Portworld · YC-SM43P** (marked Experimental) in **New screen**, and follow [Easy setup](EASY_SETUP.md).
The USB-C port is the chip's own USB, so a first install goes over USB-C and the log comes out of it too. The remote
package is `packages/portworld43p.yaml`; the checkout entry is `checkout/portworld43p.yaml`. Both combine
`packages/core.yaml` with `packages/boards/portworld43p.yaml`.

The screen joins Home Assistant over Wi-Fi. PoE powers it, but its Ethernet port is not used yet (see below).

## Layout and capabilities

- The glass has the size and resolution of the 4-inch Guition, so the screen looks the same: two columns of three cells,
  the same tiles in millimetres, the standard look at 170 dpi. The glass is square, so it turns a quarter as well as a half.
- The backlight hangs on a PWM pin of the chip (GPIO4) at 5 kHz with a 10 % floor, as Portworld's own firmware drives
  it. Brightness is a percentage, and standby, night mode, Sleep, Wake and the alert's flashes are enabled.
- Camera tiles, full-screen snapshots, live tile pictures, camera alerts and media artwork use the shared PSRAM implementation.
- GT911 reports pixel coordinates, with no resistive calibration.
- The CH390D Ethernet chip, the RS485 port, the real-time clock's interrupt and the buzzer stay unused. The AHT20 is fitted
  on some units only; [Buttons, sensors and other hardware](https://tessera-maxgramser.on-forge.com/docs/extra-hardware)
  adds it, and the buzzer, through Override YAML.

## Hardware references

Portworld does not publish a full schematic. The pins below come from the schematic extracts Portworld sent (the
ESP32-S3 module, the NCA9555 expander and the CH390D) and from the panel configuration compiled into their board library
([Portworld-tech/43p-esp32-neutral-software](https://github.com/Portworld-tech/43p-esp32-neutral-software),
`components/board_bsp`). The four data lines the extracts show (B1 GPIO5, R3 GPIO8, R4 GPIO18, R5 GPIO17) match.

- I2C: SDA GPIO15, SCL GPIO7, shared by the GT911 (0x5D), the NCA9555 expander (0x20, TCA9555 registers) and the AHT20.
- Expander port 0: P0.0 panel select, P0.1 touch reset, P0.2 panel reset, P0.3 panel data, P0.4 panel clock,
  P0.5 CH390D select, P0.6 clock interrupt, P0.7 CH390D reset. Port 1: P1.0 RS485 direction (high = transmit),
  P1.1 buzzer.
- The ST7701S takes its setup over three-wire SPI on the expander: CS P0.0, data P0.3, clock P0.4.
- RGB: DE GPIO40, PCLK GPIO41, HSYNC GPIO38, VSYNC GPIO39, 20.6 MHz pixel clock, HSYNC 8/80/80 and VSYNC 2/30/18
  (pulse/back/front), 18-bit pixel mode, RGB order, colours not inverted.
  Red GPIO46, 3, 8, 18, 17; green GPIO14, 13, 12, 11, 10, 9; blue GPIO5, 45, 48, 47, 21 (least significant first).
- Init: ESPHome's `ST7701S` sequence with Portworld's four differences after it: C2 21 08, CD 00 (the 16-bit bus; the
  model sets 08), B1 30, B2 87.
- Touch: GT911 interrupt GPIO16, reset P0.1.
- Backlight: GPIO4, PWM at 5 kHz.
- CH390D: SCK GPIO42, MOSI GPIO2, MISO GPIO1, interrupt GPIO6; select P0.5 and reset P0.7 on the expander.
- UART0 (GPIO43/44) goes to the RS485 transceiver, so the log goes over USB (`USB_SERIAL_JTAG`).

## Ethernet

ESPHome's `ethernet:` supports the CH390, but takes its select line only from a pin of the chip itself
(`internal_gpio_output_pin_number`). On this board that line is an expander output: Portworld's firmware drives it
over I2C around every SPI transfer with a custom SPI driver (`spi_bus_add_device` with no hardware CS). Wired Ethernet
therefore needs an external component that does the same, or a board revision that routes the select line to a free
chip pin. Every chip pin is taken here except GPIO0, whose required high level at boot is the select line's idle level.

## What to report while testing

1. Board revision, successful boot and appearance in Tessera.
2. The picture after a cold start and after a restart: colours, mirroring, and whether it slips sideways under a camera
   picture (if it does, try a 16 MHz pixel clock).
3. Touch in the four corners and a drag.
4. Brightness from 10 to 100 %, standby and wake.
