#pragma once

#include "esphome/core/defines.h"

#if defined(USE_ESP32) && defined(USE_ETHERNET_CH390) && defined(USE_ETHERNET_EXPANDER_CS)

#include "esphome/core/hal.h"
#include "esp_eth_mac_ch390.h"

namespace esphome::ethernet {

// Installs a CH390 SPI driver whose chip select is an ESPHome GPIOPin instead of a chip pin.
//
// On the Portworld YC-SM43P the CH390D's SCS line goes to an NCA9555 (TCA9555) IO expander, so the SPI
// peripheral cannot drive it. This driver adds the CH390 to the SPI host with no hardware chip select and
// asserts / releases `cs_pin` around every transaction, the way Portworld's own firmware does. Each edge is
// one I2C write to the expander (about 0.1 ms at 400 kHz), so throughput is far below a native chip select
// but ample for Home Assistant's API.
//
// The SPI frame format is the stock driver's: 1 command bit (0 read, 1 write) and 7 address bits.
//
// Must be called before esp_eth_mac_new_ch390(); `config` and the spi_devcfg it points at must stay alive
// until that call returns, because the driver's init() reads them back.
void install_ch390_expander_spi(eth_ch390_config_t &config, GPIOPin *cs_pin);

}  // namespace esphome::ethernet

#endif  // USE_ESP32 && USE_ETHERNET_CH390 && USE_ETHERNET_EXPANDER_CS
