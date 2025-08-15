# Pin Map — Feather ESP32‑S2 + 2.13" e‑ink FeatherWing

- SPI: SCK, MOSI, MISO → Feather defaults
- e‑ink control: EINK_CS=D9, EINK_DC=D10, EINK_BUSY=D7, EINK_RST=D8 (confirm Wing rev)
- I²C: SDA, SCL → sensors
- Optional EINK_EN: GPIO to load‑switch enable if you power‑gate display VCC

| Signal     | Pin  | Notes                  |
|------------|------|------------------------|
| EINK_CS    | D9   | Chip select            |
| EINK_DC    | D10  | Data/Command           |
| EINK_BUSY  | D7   | Busy (input)           |
| EINK_RST   | D8   | Reset                  |
| SPI_SCK    | SCK  | SPI clock              |
| SPI_MOSI   | MOSI | SPI data out           |
| SPI_MISO   | MISO | Not used by panel      |
| I2C_SDA    | SDA  | Sensors                |
| I2C_SCL    | SCL  | Sensors                |
| EINK_EN    | TBD  | Optional load switch   |

Adjust in firmware if your stack or revision differs.
