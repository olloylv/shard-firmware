/* Symbols the LXR DSP code takes from parts of the firmware that are not
 * built on the host. SPDX-License-Identifier: GPL-3.0-only */
#include <stdint.h>
#include <stdlib.h>

uint32_t GetRngValue(void)
{
	static uint32_t x = 0x12345678u;
	x ^= x << 13; x ^= x >> 17; x ^= x << 5;
	return x;
}

float midiParser_calcDetune(uint8_t value) { (void)value; return 1.f; }
