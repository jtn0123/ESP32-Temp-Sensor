#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>

extern "C" {
#include <unity.h>
}

static std::string format_one_decimal(float v) {
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%.1f", v);
  return std::string(buf);
}

static std::string format_integer(float v) {
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%.0f", v);
  return std::string(buf);
}

static int suggested_display_precision(const char* unit) {
  if (std::strcmp(unit, "°F") == 0) return 1;
  if (std::strcmp(unit, "V") == 0) return 2;
  if (std::strcmp(unit, "hPa") == 0) return 1;
  return 0;
}

static void test_c_to_f_rounding_one_decimal(void) {
  // 22.05°C -> 71.69°F -> 71.7
  float f1 = 22.05f * 9.0f / 5.0f + 32.0f;
  TEST_ASSERT_EQUAL_STRING("71.7", format_one_decimal(f1).c_str());

  // 22.04°C -> 71.672°F -> 71.7 (round half up)
  float f2 = 22.04f * 9.0f / 5.0f + 32.0f;
  TEST_ASSERT_EQUAL_STRING("71.7", format_one_decimal(f2).c_str());

  // 22.00°C -> 71.6°F -> 71.6
  float f3 = 22.00f * 9.0f / 5.0f + 32.0f;
  TEST_ASSERT_EQUAL_STRING("71.6", format_one_decimal(f3).c_str());
}

static void test_humidity_integer_rounding(void) {
  TEST_ASSERT_EQUAL_STRING("42", format_integer(41.5f).c_str());
  TEST_ASSERT_EQUAL_STRING("42", format_integer(41.6f).c_str());
  TEST_ASSERT_EQUAL_STRING("41", format_integer(41.4f).c_str());
  TEST_ASSERT_EQUAL_STRING("0", format_integer(0.49f).c_str());
  TEST_ASSERT_EQUAL_STRING("1", format_integer(0.5f).c_str());
}

static void test_suggested_precision_mapping(void) {
  TEST_ASSERT_EQUAL_INT(1, suggested_display_precision("°F"));
  TEST_ASSERT_EQUAL_INT(0, suggested_display_precision("%"));
  TEST_ASSERT_EQUAL_INT(2, suggested_display_precision("V"));
  TEST_ASSERT_EQUAL_INT(1, suggested_display_precision("hPa"));
}

void setUp(void) {}
void tearDown(void) {}

int main(int argc, char** argv) {
  (void)argc; (void)argv;
  UNITY_BEGIN();
  RUN_TEST(test_c_to_f_rounding_one_decimal);
  RUN_TEST(test_humidity_integer_rounding);
  RUN_TEST(test_suggested_precision_mapping);
  return UNITY_END();
}


