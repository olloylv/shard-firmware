/* Host (x86) stand-in for the STM32 HAL, only what the DSP code needs.
 * SPDX-License-Identifier: GPL-3.0-only */
#ifndef HOST_STM32F7XX_HAL_H_
#define HOST_STM32F7XX_HAL_H_
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

typedef struct { int dummy; } RNG_HandleTypeDef;
typedef struct { int dummy; } TIM_HandleTypeDef;
typedef enum { HAL_OK = 0, HAL_ERROR } HAL_StatusTypeDef;
#define __IO volatile
#define UNUSED(x) ((void)(x))

static inline int32_t __SSAT(int32_t v, uint32_t bits) {
	const int32_t max = (1 << (bits - 1)) - 1, min = -(1 << (bits - 1));
	return v > max ? max : (v < min ? min : v);
}
static inline int16_t host_sat16(int32_t v) { return (int16_t)(v > 32767 ? 32767 : (v < -32768 ? -32768 : v)); }
static inline uint32_t __QADD16(uint32_t a, uint32_t b) {
	const int16_t lo = host_sat16((int32_t)(int16_t)(a & 0xffff) + (int16_t)(b & 0xffff));
	const int16_t hi = host_sat16((int32_t)(int16_t)(a >> 16) + (int16_t)(b >> 16));
	return ((uint32_t)(uint16_t)hi << 16) | (uint16_t)lo;
}
static inline uint32_t __QSUB16(uint32_t a, uint32_t b) {
	const int16_t lo = host_sat16((int32_t)(int16_t)(a & 0xffff) - (int16_t)(b & 0xffff));
	const int16_t hi = host_sat16((int32_t)(int16_t)(a >> 16) - (int16_t)(b >> 16));
	return ((uint32_t)(uint16_t)hi << 16) | (uint16_t)lo;
}
static inline uint32_t __SADD16(uint32_t a, uint32_t b) {
	const int16_t lo = (int16_t)((int16_t)(a & 0xffff) + (int16_t)(b & 0xffff));
	const int16_t hi = (int16_t)((int16_t)(a >> 16) + (int16_t)(b >> 16));
	return ((uint32_t)(uint16_t)hi << 16) | (uint16_t)lo;
}
static inline uint32_t __PKHBT(uint32_t a, uint32_t b, uint32_t shift) {
	return (a & 0xffff) | ((b << shift) & 0xffff0000u);
}
static inline int32_t __QADD(int32_t a, int32_t b) { int64_t s = (int64_t)a + b; return s > 2147483647 ? 2147483647 : (s < -2147483647 - 1 ? -2147483647 - 1 : (int32_t)s); }
typedef union { struct { uint32_t _r:28; uint32_t V:1; uint32_t C:1; uint32_t Z:1; uint32_t N:1; } b; uint32_t w; } APSR_Type;
static inline uint32_t __get_APSR(void) { return 0; }
static inline uint8_t __CLZ(uint32_t v) { return v ? (uint8_t)__builtin_clz(v) : 32; }
static inline uint32_t HAL_GetTick(void) { return 0; }
#endif
