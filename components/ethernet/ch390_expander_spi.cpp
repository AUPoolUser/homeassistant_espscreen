#include "ch390_expander_spi.h"

#if defined(USE_ESP32) && defined(USE_ETHERNET_CH390) && defined(USE_ETHERNET_EXPANDER_CS)

#include <driver/spi_master.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include "esphome/core/log.h"

namespace esphome::ethernet {

namespace {

static const char *const TAG = "ethernet.ch390";

// Context returned by init() and handed back to read/write/deinit. There is one CH390 per device, so a single
// static instance replaces a heap allocation; it is cleared again by deinit().
struct Ch390ExpanderSpiContext {
  spi_device_handle_t handle;
  SemaphoreHandle_t lock;
  GPIOPin *cs;
};
// NOLINTNEXTLINE(cppcoreguidelines-avoid-non-const-global-variables) - intentional mutable state
Ch390ExpanderSpiContext ch390_context{};
// The chip select handed to install_ch390_expander_spi(), picked up by init().
// NOLINTNEXTLINE(cppcoreguidelines-avoid-non-const-global-variables) - intentional mutable state
GPIOPin *ch390_pending_cs = nullptr;

// Longer than the stock driver's 50 ms: a transaction also waits for the I2C bus, which the touch
// controller and sensors share with the expander.
constexpr uint32_t CH390_SPI_LOCK_TIMEOUT_MS = 200;

void *ch390_expander_spi_init(const void *spi_config) {
  const auto *config = static_cast<const eth_ch390_config_t *>(spi_config);
  auto *ctx = &ch390_context;
  if (ch390_pending_cs == nullptr) {
    ESP_LOGE(TAG, "No chip select pin");
    return nullptr;
  }
  spi_device_interface_config_t devcfg = *config->spi_devcfg;
  devcfg.command_bits = 1;  // the CH390 frame: R/W bit
  devcfg.address_bits = 7;  // then the register address
  devcfg.spics_io_num = -1;  // chip select is ours, on the expander
  if (spi_bus_add_device(config->spi_host_id, &devcfg, &ctx->handle) != ESP_OK) {
    ESP_LOGE(TAG, "Adding the CH390 to SPI host %d failed", config->spi_host_id + 1);
    ctx->handle = nullptr;
    return nullptr;
  }
  ctx->lock = xSemaphoreCreateMutex();
  if (ctx->lock == nullptr) {
    spi_bus_remove_device(ctx->handle);
    ctx->handle = nullptr;
    return nullptr;
  }
  ctx->cs = ch390_pending_cs;
  ctx->cs->digital_write(true);  // released
  return ctx;
}

esp_err_t ch390_expander_spi_deinit(void *spi_ctx) {
  auto *ctx = static_cast<Ch390ExpanderSpiContext *>(spi_ctx);
  spi_bus_remove_device(ctx->handle);
  vSemaphoreDelete(ctx->lock);
  *ctx = {};
  return ESP_OK;
}

// One transaction framed by the chip select, under the device lock.
esp_err_t ch390_expander_spi_transfer(Ch390ExpanderSpiContext *ctx, spi_transaction_t *trans) {
  if (xSemaphoreTake(ctx->lock, pdMS_TO_TICKS(CH390_SPI_LOCK_TIMEOUT_MS)) != pdTRUE) {
    return ESP_ERR_TIMEOUT;
  }
  ctx->cs->digital_write(false);
  esp_err_t ret = spi_device_polling_transmit(ctx->handle, trans);
  ctx->cs->digital_write(true);
  xSemaphoreGive(ctx->lock);
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "SPI transfer failed: %s", esp_err_to_name(ret));
  }
  return ret;
}

esp_err_t ch390_expander_spi_write(void *spi_ctx, uint32_t cmd, uint32_t addr, const void *data, uint32_t len) {
  auto *ctx = static_cast<Ch390ExpanderSpiContext *>(spi_ctx);
  spi_transaction_t trans = {};
  trans.cmd = static_cast<uint16_t>(cmd);
  trans.addr = addr;
  trans.length = 8 * len;
  trans.tx_buffer = data;
  return ch390_expander_spi_transfer(ctx, &trans);
}

esp_err_t ch390_expander_spi_read(void *spi_ctx, uint32_t cmd, uint32_t addr, void *data, uint32_t len) {
  auto *ctx = static_cast<Ch390ExpanderSpiContext *>(spi_ctx);
  spi_transaction_t trans = {};
  trans.cmd = static_cast<uint16_t>(cmd);
  trans.addr = addr;
  trans.length = 8 * len;
  trans.rx_buffer = data;
  return ch390_expander_spi_transfer(ctx, &trans);
}

}  // namespace

void install_ch390_expander_spi(eth_ch390_config_t &config, GPIOPin *cs_pin) {
  ch390_pending_cs = cs_pin;
  // init() reads spi_host_id and spi_devcfg back out of the CH390 config itself.
  config.custom_spi_driver.config = &config;
  config.custom_spi_driver.init = ch390_expander_spi_init;
  config.custom_spi_driver.deinit = ch390_expander_spi_deinit;
  config.custom_spi_driver.read = ch390_expander_spi_read;
  config.custom_spi_driver.write = ch390_expander_spi_write;
}

}  // namespace esphome::ethernet

#endif  // USE_ESP32 && USE_ETHERNET_CH390 && USE_ETHERNET_EXPANDER_CS
