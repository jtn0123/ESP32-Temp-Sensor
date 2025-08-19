#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_EPD.h>

#ifndef EPD_CS
#define EPD_CS 9
#endif
#ifndef EPD_DC
#define EPD_DC 10
#endif
#ifndef EPD_BUSY
#define EPD_BUSY 7
#endif
#ifndef EPD_RST
#define EPD_RST -1
#endif

// 2.13" mono SSD1680 (GDEY0213B74) per Adafruit FeatherWing
Adafruit_SSD1680 display(250, 122, EPD_DC, EPD_RST, EPD_CS, -1, EPD_BUSY);

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("Adafruit FeatherWingTest (SSD1680) start");

  display.begin();
  display.setRotation(1); // landscape 250x122

  display.clearBuffer();
  display.fillScreen(EPD_WHITE);
  display.setTextColor(EPD_BLACK);
  display.setTextSize(1);
  display.setCursor(10, 10);
  display.print("FeatherWingTest");
  display.setCursor(10, 30);
  display.print("SSD1680 250x122");
  display.setCursor(10, 50);
  display.print("Hello from Adafruit_EPD");
  display.display();
  Serial.println("EPD first frame drawn");
}

void loop() {
  // No deep sleep here; just idle and keep USB alive
  delay(1000);
}


