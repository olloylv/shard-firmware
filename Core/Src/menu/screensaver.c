/*
 * screensaver.c
 *
 * Created: 25.01.2013 17:08:02
 *  Author: Julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */ 
//to expand the lifetime of OLED displays, we need a timeout var to go to
//screensaver mode if the controls are not touched for a while
#include "lcd.h"
#include "menu/screensaver.h"

#include "menu/menu.h"
#include "delay.h"
#include "graphic.h"
#include "Soundengine/Soundengine.h"
#include "Shard/sh_channel.h"
#include <math.h>
#include <string.h>

/* SHARD: level meters of the six channels instead of the dots */
#define SHARD_SCREENSAVER 1

#define SCREENSAVER_ACTIVE 1

//stuff for activation logic
volatile uint32_t screensaver_timer = 0;
#define SCREENSAVER_TIMEOUT 2//[minutes]
#define SCREENSAVER_SYSTICK (uint32_t)(((SCREENSAVER_TIMEOUT*60) *1000))/// (1.f / ((F_CPU/1024.f)/256.f))))
volatile uint8_t screensaver_Active=0;
volatile uint32_t screensaver_Timeout=SCREENSAVER_SYSTICK;


//stuff for fancy drawing
static __attribute__((unused)) uint32_t screensaver_processTime = 0;
#define SCREENSAVER_PROCESS_SPEED 500//((0.5) / (1.f / ((F_CPU/1024.f)/256.f)))
enum
{
	CELL_NEW_POS,
	CELL_OFF,
	CELL_OFF_WAIT,
	CELL_1_SET_CURSOR,
	CELL_1_PRINT,
	CELL_1_WAIT,
	CELL_2_SET_CURSOR,
	CELL_2_PRINT,
	CELL_2_WAIT,
	CELL_3_SET_CURSOR,
	CELL_3_PRINT,
	CELL_3_WAIT,


};

uint8_t screensaver_activeCell = 0;
uint8_t screensaver_cellState = CELL_OFF;

uint16_t screensaver_rng =  0;	//*<temporary var for rng generation*/
//------------------------------------------------------------------
uint8_t screensaver_pseudoRng()
{
	screensaver_rng++;
	screensaver_rng *= 3;
	return (screensaver_rng >> 2) & 0xFF;
}
//------------------------------------------------------------------
void screensaver_touch()
{
	screensaver_timer = 0;
	screensaver_Timeout = SCREENSAVER_SYSTICK;

	if(screensaver_Active)
	{
		//while(sendDisplayBuffer() != 0); //wrong! we wan't to clean the screensaver pipeline, noit the normal menu one!
#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Start_IT(&htim2);	//calc sample interrupt - prio 1
#endif
		while(screensaver_process() != 0) soundengine_process();
		sh_meterEnable(0);

#if USE_INTERRUPT_ONLY_DURING_SAVE_PROJ
	HAL_TIM_Base_Stop_IT(&htim2);	//calc sample interrupt - prio 1
#endif
		//lcd_turnOn(1,0);
		screensaver_Active = 0;
		menu_repaintAll();
	}	
}
//------------------------------------------------------------------
//draw some fancy stuff on the LCD


Framebuffer framebuffer[2][8];
uint8_t x=0;
uint8_t y = 0;

#if SHARD_SCREENSAVER
/* Six vertical bars, one per channel, two LCD rows high (16 pixel steps).
 * A bar jumps up with the channel's peak level and falls back slowly. The
 * group of bars drifts sideways every few seconds so no pixel stays lit.
 * Everything uses the non blocking LCD calls, one call per pass. */
enum { SS_CLEAR = 0, SS_CHARS, SS_WAIT, SS_CUR1, SS_ROW1, SS_CUR2, SS_ROW2 };
#define SS_FRAME_MS 40
#define SS_SHIFT_MS 7000

static uint8_t ss_char;
static uint8_t ss_pos;
static uint8_t ss_charData[8];
static uint8_t ss_level[SH_NUM_CHANNELS];
static uint8_t ss_offset;
static int8_t ss_dir = 1;
static uint32_t ss_nextFrame, ss_nextShift;
static char ss_rows[2][16];

static void ss_buildChar(uint8_t k)
{
	/* character k: bar of height k+1 pixels from the bottom */
	for(uint8_t r = 0; r < 8; r++)
		ss_charData[r] = (uint8_t)((r >= 7 - k) ? 0x1F : 0x00);
}

static void ss_frame(void)
{
	const uint32_t now = HAL_GetTick();
	if(now >= ss_nextShift)
	{
		ss_nextShift = now + SS_SHIFT_MS;
		if((ss_dir > 0 && ss_offset >= 5) || (ss_dir < 0 && ss_offset == 0)) ss_dir = (int8_t)-ss_dir;
		ss_offset = (uint8_t)(ss_offset + ss_dir);
	}
	memset(ss_rows, ' ', sizeof(ss_rows));
	for(uint8_t ch = 0; ch < SH_NUM_CHANNELS; ch++)
	{
		const uint16_t pk = sh_meterTake(ch);
		/* -54 dB .. 0 dB -> 0 .. 16 */
		uint8_t target = 0;
		if(pk > 64)
		{
			const float l = (log2f((float)pk) - 6.f) * (16.f / 9.f);
			target = (uint8_t)(l > 16.f ? 16.f : (l < 1.f ? 1.f : l));
		}
		uint8_t lvl = ss_level[ch];
		lvl = target >= lvl ? target : (uint8_t)(lvl - 1);
		ss_level[ch] = lvl;

		const uint8_t col = (uint8_t)(ss_offset + 2 * ch);
		if(lvl >= 8) ss_rows[1][col] = 7;
		else if(lvl) ss_rows[1][col] = (char)(lvl - 1);
		if(lvl > 8) ss_rows[0][col] = (char)(lvl - 9);
	}
}

static uint8_t ss_process(void)
{
	switch(screensaver_cellState)
	{
	default:
	case SS_CLEAR:
		while(sendDisplayBuffer() != 0);
		if(lcd_clear_nonblock())
		{
			ss_char = 0;
			ss_buildChar(0);
			screensaver_cellState = SS_CHARS;
			return 0;
		}
		return 1;

	case SS_CHARS:
		if(lcd_generatechar_nonBlock(ss_char, ss_charData))
		{
			if(++ss_char >= 8)
			{
				memset(ss_level, 0, sizeof(ss_level));
				for(uint8_t ch = 0; ch < SH_NUM_CHANNELS; ch++) sh_meterTake(ch);
				sh_meterEnable(1);
				ss_nextFrame = HAL_GetTick();
				screensaver_cellState = SS_WAIT;
			}
			else ss_buildChar(ss_char);
			return 0;
		}
		return 1;

	case SS_WAIT:
		if(HAL_GetTick() >= ss_nextFrame)
		{
			ss_nextFrame = HAL_GetTick() + SS_FRAME_MS;
			ss_frame();
			screensaver_cellState = SS_CUR1;
		}
		return 0;

	case SS_CUR1:
	case SS_CUR2:
		if(lcd_setcursor_nonBlock(0, screensaver_cellState == SS_CUR1 ? 1 : 2))
		{
			ss_pos = 0;
			screensaver_cellState++;
			return 0;
		}
		return 1;

	case SS_ROW1:
	case SS_ROW2:
		if(lcd_data_nonBlock((uint8_t)ss_rows[screensaver_cellState == SS_ROW1 ? 0 : 1][ss_pos]))
		{
			if(++ss_pos >= 16)
				screensaver_cellState = screensaver_cellState == SS_ROW1 ? SS_CUR2 : SS_WAIT;
			return 0;
		}
		return 1;
	}
}
#endif

uint8_t screensaver_process()
{

#if SHARD_SCREENSAVER
	return ss_process();
#elif PLASMA_SCREENSAVER
	switch(screensaver_cellState)
	{
	case 0:
		if(lcd_clear_nonblock())
		{
			screensaver_cellState++;
		}
		break;

	case 1:
		//print custom characters
		lcd_home();
		lcd_clear();
		lcd_setcursor(0,1);
		lcd_data(0);
		lcd_data(1);
		lcd_data(2);
		lcd_data(3);
		lcd_data(0);
		lcd_data(1);
		lcd_data(2);
		lcd_data(3);
		lcd_data(0);
		lcd_data(1);
		lcd_data(2);
		lcd_data(3);
		lcd_data(0);
		lcd_data(1);
		lcd_data(2);
		lcd_data(3);

		lcd_setcursor(0,2);
		lcd_data(4);
		lcd_data(5);
		lcd_data(6);
		lcd_data(7);
		lcd_data(4);
		lcd_data(5);
		lcd_data(6);
		lcd_data(7);
		lcd_data(4);
		lcd_data(5);
		lcd_data(6);
		lcd_data(7);
		lcd_data(4);
		lcd_data(5);
		lcd_data(6);
		lcd_data(7);
		screensaver_cellState++;
		break;

	case 2:
	{
		graphic_tick();
		//if(HAL_GetTick() >= screensaver_processTime )
		{
		//update framebuffer

		//send framebuffer
	    // Startposition des Zeichens einstellen


			lcd_command( LCD_SET_CGADR | (uint8_t)(0<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[0][i].chars.char1 );
			}

			lcd_command( LCD_SET_CGADR | (uint8_t)(1<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[0][i].chars.char2 );
			}

			lcd_command( LCD_SET_CGADR | (uint8_t)(2<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[0][i].chars.char3 );
			}

			lcd_command( LCD_SET_CGADR | (uint8_t)(3<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[0][i].chars.char4 );
			}

			lcd_command( LCD_SET_CGADR | (uint8_t)(4<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[1][i].chars.char1 );
			}

			lcd_command( LCD_SET_CGADR | (uint8_t)(5<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[1][i].chars.char2 );
			}

			lcd_command( LCD_SET_CGADR | (uint8_t)(6<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[1][i].chars.char3 );
			}

			lcd_command( LCD_SET_CGADR | (uint8_t)(7<<3) );
			// Bitmuster uebertragen
			for ( uint8_t i=0; i<8; i++ )
			{
				lcd_data( framebuffer[1][i].chars.char4 );
			}

			screensaver_cellState++;
		}
		}
	break;

	case 3:
		//generate new gfx
#if 0
	{


		uint8_t row = y>7?1:0;

		framebuffer[row][y%8].itg |= (1<<(19-x));

		x++;
		if(x>=20)
		{
			x=0;
			y++;
			if(y>=16) y=0;
		}
	}
#elif 1
		for(uint8_t y=0;y<16;y++)
		{
			uint8_t row = y>7?1:0;

			for(uint8_t x=0;x<20;x++)
			{

				uint8_t value = graphic_calcPlasma(x,y);
				if(value)
				{
					//set pixel
					framebuffer[row][y%8].itg |= (1<<(19-x));
				}
				else
				{
					//remove pixel
					framebuffer[row][y%8].itg &= ~(1<<(19-x));
				}
			}
		}
#else
		graphic_drawLineArt(framebuffer);
#endif
		screensaver_processTime = ( HAL_GetTick() + SCREENSAVER_PROCESS_SPEED);


		screensaver_cellState = 2;
		break;

	}





#else
	char text[2];
	text[1] = 0;

	while(sendDisplayBuffer() != 0);

	switch(screensaver_cellState)
	{
		default:
			break;

		case CELL_NEW_POS:
			if(HAL_GetTick() >= screensaver_processTime )
			{
				screensaver_processTime = ( HAL_GetTick() + SCREENSAVER_PROCESS_SPEED);


				screensaver_activeCell = screensaver_pseudoRng()&0x1f; //value between 0 and 31

				screensaver_cellState = CELL_OFF;
				return 0;
			}
			break;

			case CELL_OFF:
				//lcd_clear();
				if(lcd_clear_nonblock())
				{
					screensaver_processTime = ( HAL_GetTick() + SCREENSAVER_PROCESS_SPEED);
					screensaver_cellState = CELL_OFF_WAIT;
					return 0;
				}
				break;

			case CELL_OFF_WAIT:
				if(HAL_GetTick() >= screensaver_processTime )
				{
					screensaver_cellState = CELL_1_SET_CURSOR;
					return 0;
				}
				break;

			case CELL_1_SET_CURSOR:
				if(screensaver_activeCell>15)
				{
					if(lcd_setcursor_nonBlock((uint8_t)(screensaver_activeCell-16),2))
					{
						screensaver_cellState = CELL_1_PRINT;
						return 0;
					}
				}
				else
				{
					if(lcd_setcursor_nonBlock(screensaver_activeCell,1))
					{
						screensaver_cellState = CELL_1_PRINT;
						return 0;
					}
				}
			break;

			case CELL_1_PRINT:
				text[0] = '.'; //.
				//lcd_string(text);
				if(lcd_data_nonBlock(text[0]))
				{
					screensaver_processTime = ( HAL_GetTick() + SCREENSAVER_PROCESS_SPEED);
					screensaver_cellState = CELL_1_WAIT;
					return 0;
				}
				break;

			case CELL_1_WAIT:
				if(HAL_GetTick() >= screensaver_processTime )
				{
					screensaver_cellState = CELL_2_SET_CURSOR;
					return 0;
				}
				break;

			case CELL_2_SET_CURSOR:
				if(screensaver_activeCell>15)
				{
					if(lcd_setcursor_nonBlock((uint8_t)(screensaver_activeCell-16),2))
					{
						screensaver_cellState = CELL_2_PRINT;
						return 0;
					}
				}
				else
				{
					if(lcd_setcursor_nonBlock(screensaver_activeCell,1))
					{

						screensaver_cellState = CELL_2_PRINT;
						return 0;
					}
				}
			break;

			case CELL_2_PRINT:
				text[0] = 'o'; //o
				//lcd_string(text);
				if(lcd_data_nonBlock(text[0]))
				{
					screensaver_processTime = ( HAL_GetTick() + SCREENSAVER_PROCESS_SPEED);
					screensaver_cellState = CELL_2_WAIT;
					return 0;
				}

			break;

			case CELL_2_WAIT:
				if(HAL_GetTick() >= screensaver_processTime )
				{
					screensaver_cellState = CELL_3_SET_CURSOR;
					return 0;
				}
				break;

			case CELL_3_SET_CURSOR:
				if(screensaver_activeCell>15)
				{
					if(lcd_setcursor_nonBlock((uint8_t)(screensaver_activeCell-16),2))
					{
						screensaver_cellState = CELL_3_PRINT;
						return 0;
					}
				}
				else
				{
					if(lcd_setcursor_nonBlock(screensaver_activeCell,1))
					{
						screensaver_cellState = CELL_3_PRINT;
						return 0;
					}
				}
			break;

			case CELL_3_PRINT:
			text[0] = '*'; //pop
			//lcd_string(text);
			if(lcd_data_nonBlock(text[0]))
			{
				screensaver_processTime = ( HAL_GetTick() + SCREENSAVER_PROCESS_SPEED);
				screensaver_cellState = CELL_NEW_POS;
				return 0;
			}

			break;
	}


	return 1;
#endif
}
//------------------------------------------------------------------
void screensaver_check()
{
	if(activeParameters[PAR_SCREENSAVER_ON_OFF])
	{
		if( (!screensaver_Active) )
		{
			if(screensaver_timer >= screensaver_Timeout)
			{
				//lcd_turnOn(0,0);
				screensaver_Active = 1;	
				screensaver_cellState = 0;
			}
		}
		else
		{
			screensaver_process();
		}	
	}
};
//------------------------------------------------------------------
