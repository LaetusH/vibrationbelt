#include "pdm_capture.h"

#include <Arduino.h>
#include <driver/i2s_pdm.h>
#include <esp_err.h>

#include "config.h"

namespace pdm {
namespace {

i2s_chan_handle_t g_rx_chan = nullptr;

// IM69D130 PDM clock policy:
//   - The driver's I2S_PDM_RX_CLK_DEFAULT_CONFIG() selects
//     dn_sample_mode = I2S_PDM_DSR_8S, which produces a PDM clock at
//     SAMPLE_RATE × 128. For 16 kHz audio that's 2.048 MHz — well inside
//     the IM69D130's "normal-power" band (≳1 MHz, per Infineon datasheet
//     v01.00). Below that the mic enters low-power mode and SNR drops.
//   - We make the choice explicit (and adjustable) rather than relying on
//     the macro's default, so the comment lives next to the constant.
constexpr i2s_pdm_dsr_t PDM_DOWNSAMPLE = I2S_PDM_DSR_8S;   // PDM CLK = fs × 128

}  // namespace

void init() {
    // ── Step 1: allocate an I²S channel ─────────────────────────────────
    // Classic ESP32 PDM RX lives on I2S_NUM_0. Specifying it explicitly
    // (rather than I2S_NUM_AUTO) prevents the driver from picking I2S_NUM_1
    // on chips where both controllers exist, which would silently disable PDM.
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(
        I2S_NUM_0, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num  = cfg::DMA_DESC_NUM;
    chan_cfg.dma_frame_num = cfg::DMA_FRAME_NUM;
    chan_cfg.auto_clear    = false;

    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, /*tx=*/nullptr, &g_rx_chan));

    // ── Step 2: configure PDM-RX mode on that channel ──────────────────
    // Slot mode derived from cfg::CHANNELS; see config.h for why CHANNELS=1
    // is the only sane choice on classic ESP32 today.
    constexpr auto slot_mode = (cfg::CHANNELS == 2)
        ? I2S_SLOT_MODE_STEREO
        : I2S_SLOT_MODE_MONO;

    i2s_pdm_rx_clk_config_t clk_cfg = I2S_PDM_RX_CLK_DEFAULT_CONFIG(
        cfg::SAMPLE_RATE_HZ);
    clk_cfg.dn_sample_mode = PDM_DOWNSAMPLE;

    i2s_pdm_rx_config_t pdm_cfg = {
        .clk_cfg  = clk_cfg,
        .slot_cfg = I2S_PDM_RX_SLOT_DEFAULT_CONFIG(
            I2S_DATA_BIT_WIDTH_16BIT, slot_mode),
        .gpio_cfg = {
            .clk = static_cast<gpio_num_t>(cfg::PDM_CLK_PIN),
            .din = static_cast<gpio_num_t>(cfg::PDM_DATA_PIN),
            .invert_flags = { .clk_inv = false },
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_pdm_rx_mode(g_rx_chan, &pdm_cfg));

    // ── Step 3: start the DMA ──────────────────────────────────────────
    ESP_ERROR_CHECK(i2s_channel_enable(g_rx_chan));

    // Effective PDM clock (for sanity-checking the log against the
    // IM69D130 datasheet's recommended 1–3.5 MHz range).
    const uint32_t oversample = (PDM_DOWNSAMPLE == I2S_PDM_DSR_8S) ? 128 : 64;
    const uint32_t pdm_clk_hz = cfg::SAMPLE_RATE_HZ * oversample;

    Serial.printf(
        "[pdm] init OK  rate=%u Hz  %s 16-bit  PDM_CLK=%lu Hz (%ux ovs)\n",
        (unsigned)cfg::SAMPLE_RATE_HZ,
        cfg::CHANNELS == 2 ? "stereo" : "mono",
        (unsigned long)pdm_clk_hz, (unsigned)oversample);
    Serial.printf("[pdm]   pins: clk=GPIO%d  din=GPIO%d\n",
                  cfg::PDM_CLK_PIN, cfg::PDM_DATA_PIN);

    // ── Step 4: warm-up ─────────────────────────────────────────────────
    // Discard the first ~MIC_WARMUP_MS of samples so the receiver doesn't
    // hear the mic's startup transient as a loud "thump".
    if (cfg::MIC_WARMUP_MS > 0) {
        constexpr size_t BYTES_PER_FRAME = cfg::CHANNELS * sizeof(int16_t);
        const uint32_t warmup_bytes =
            (cfg::SAMPLE_RATE_HZ * cfg::MIC_WARMUP_MS / 1000) * BYTES_PER_FRAME;
        uint8_t scratch[512];
        uint32_t drained = 0;
        while (drained < warmup_bytes) {
            size_t want = (warmup_bytes - drained) > sizeof(scratch)
                          ? sizeof(scratch) : (warmup_bytes - drained);
            size_t got = 0;
            if (i2s_channel_read(g_rx_chan, scratch, want, &got,
                                 pdMS_TO_TICKS(200)) != ESP_OK) break;
            drained += got;
        }
        Serial.printf("[pdm] warmup: discarded %lu bytes (~%u ms)\n",
                      (unsigned long)drained, (unsigned)cfg::MIC_WARMUP_MS);
    }
}

size_t read(void* dst, size_t bytes) {
    size_t bytes_read = 0;
    esp_err_t err = i2s_channel_read(g_rx_chan, dst, bytes,
                                     &bytes_read, portMAX_DELAY);
    if (err != ESP_OK) {
        Serial.printf("[pdm] i2s_channel_read err=%d\n", err);
        return 0;
    }
    return bytes_read;
}

}  // namespace pdm
