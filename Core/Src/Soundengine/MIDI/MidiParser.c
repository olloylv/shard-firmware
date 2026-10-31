/*
 * MidiParser.c
 *
 *  Created on: 02.04.2012
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */


#include <Soundengine/MIDI/CortexParser.h>
#include "Soundengine/MIDI/MidiParser.h"
#include "Soundengine/MIDI/MidiNoteNumbers.h"
#include "Soundengine/config.h"
#include "Soundengine/MIDI/Uart.h"
//#include "Soundengine/Sequencer/sequencer.h"
//#include "Soundengine/Sequencer/clockSync.h"
#include "Soundengine/DSPAudio/mixer.h"
#include "Soundengine/MIDI/valueShaper.h"

#include "menu/menu.h"
#include "Soundengine/FxBus.h"
#include "Parameters.h"
#include "IO/DIO.h"

static uint16_t midiParser_activeNrpnNumber = 0;

uint8_t midiParser_originalCcValues[0xff];

// this will be set to some value if we are ignoring all mtc messages until the next 0 message
//static uint8_t midiParser_mtcIgnore=1;
static uint32_t volatile midiParser_lastMtcReceived=0x0;
//static uint8_t midiParser_mtcIsRunning=0;

static union {
	uint8_t value;
	struct {
		unsigned usb2midi:1;
		unsigned usb2usb:1;   // not used
		unsigned midi2midi:1;
		unsigned midi2usb:1;
		unsigned :4;
	} route;
} midiParser_routing = {0};



//tx is high nibble
uint8_t midiParser_txRxFilter = 0xFF;

enum State
{
	MIDI_STATUS,  		// waiting for status byte
	MIDI_DATA1,  		// waiting for data byte1
	MIDI_DATA2,  		// waiting for data byte2
	SYSEX_DATA,  		// read sysex data byte
	IGNORE				// set when unknown status byte received, stays in ignore mode until next known status byte
  };

// 2^(1/12) factor for 1 semitone
#define SEMITONE_UP 1.0594630943592952645618252949463f
#define SEMITONE_DOWN 0.94387431268169349664191315666753f

#define NUM_LFO 6
uint8_t midiParser_selectedLfoVoice[NUM_LFO] = {0,0,0,0,0,0};

#if 0
// for debugging
void midiDebugSend(uint8_t b1, uint8_t b2)
{
	uart_sendMidiByte(0xF2);
	uart_sendMidiByte(b1&0x7F);
	uart_sendMidiByte(b2&0x7F);
}
#endif

//----------------------------------------------------------
#if 0
inline uint16_t calcSlopeEgTime(uint8_t data2)
{
	float val = (data2+1)/128.f;
	return data2>0?val*val*data2*128:1;
}
#endif
//-----------------------------------------------------------
static inline float calcPitchModAmount(uint8_t data2)
{
	const float val = data2/127.f;
	return val*val*PITCH_AMOUNT_FACTOR;
}

//-----------------------------------------------------------
// vars
//-----------------------------------------------------------
uint8_t midi_MidiChannels[8];	// the currently selected midi channel for each voice (element 7 is global channel)

// note overrides for each voice
//uint8_t midi_NoteOverride[7];
//uint8_t midi_mode; // not used anymore
MidiMsg midiMsg_tmp;				// buffer message where the incoming data is stored
// these two are used only when building up a midi message
//static uint8_t msgLength;					// number of following data bytes expected for current status
static uint8_t parserState = IGNORE;	// state of the parser state machine. Set to what it's expecting next
										// we set it to ignore initially so that any random data we get before
										// a valid msg header is ignored

//-----------------------------------------------------------
//takes a midi value from 0 to 127 and return +/- 50 cent detune factor
float midiParser_calcDetune(uint8_t value)
{
	//linear interpolation between 1(no change) and semitone up/down)
	float frac = (value/127.f -0.5f);
	float cent = 1;
	if(cent>=0)
	{
		cent += frac*(SEMITONE_UP - 1);
	}
	else
	{
		cent += frac*(SEMITONE_UP - 1);
	}
	return cent;
}
//-----------------------------------------------------------
__attribute__((unused)) static void midiParser_nrpnHandler(uint16_t value)
{
	MidiMsg msg2;
	msg2.status = MIDI_CC2;
	msg2.data1 = midiParser_activeNrpnNumber;
	msg2.data2 = value;
	midiParser_ccHandler(msg2,true, 0, 0.f);
}
//-----------------------------------------------------------
/* takes a [0:1] value from the CV ADC and converts it to freq information
 * CV input range is [-5V:5V] so it should span +/- 5 octaves
 */

#define QUANTIZE_CV 1

#define INPUT_VOLTAGE			3.3f	//Volt
#define OCTAVES				5.f	//octaves
#define VOLT_PER_OCTAVE			(INPUT_VOLTAGE/OCTAVES) // 1
#define VOLT_PER_NOTE			(VOLT_PER_OCTAVE/12.f)  // 0,08333333333333333333
#define VOLT_PER_ADC_STEP		(INPUT_VOLTAGE/4096.f)  // 0,000244140625
#define ADC_STEPS_PER_NOTE		(VOLT_PER_NOTE/VOLT_PER_ADC_STEP) //341,33333333333333331968


const float base_a4=440.f; // set A4=440Hz

/** handle all incoming CCs and invoke action*/
void midiParser_ccHandler(MidiMsg msg, uint8_t updateOriginalValue, uint8_t isFloatModulator, float v)
{
	/* SHARD: sound parameters are no longer pushed into the voices through CC
	 * messages. The channel strips read activeParameters directly every audio
	 * block, the FX bus is updated by midiParser_setFxParam() and the CV
	 * matrix by CV_process(). The MIDI CC/NRPN path is not used on the
	 * Eurorack module (it has no MIDI input). */
	(void)msg; (void)updateOriginalValue; (void)isFloatModulator; (void)v;
}
//-----------------------------------------------------------
void midiParser_setFxParam(uint16_t paramNr, uint8_t value)
{
	const float flt = value / 127.f;
	switch(paramNr)
	{
	case PAR_FX_TYPE:
#if USE_REVERB
		if((value == FX_REVERB) && (fxBus.fxType != value)) FxBus_prepareFxChange();
#else
		if(fxBus.fxType != value) FxBus_prepareFxChange();
#endif
		fxBus.fxType = value;
		FxBus_updateParameter();
		//change visible parameters to selected FX type
		if(menu_activePage == FX_MODE_PAGE)
		{
			if(menu_getSubPage() != fxBus.fxType)
				menu_switchSubPage(fxBus.fxType, 1);
		}
		break;
	case PAR_FX_ROUTING:     fxBus.audioRouting = value; break;
	case PAR_FX_DRY_WET:     fxBus.dryWet = value / 100.f; break;
	case PAR_FX_DIST_TYPE:   fxBus.distortion.distortionType = value; break;
	case PAR_FX_P1:          FxBus_setParameter(0, flt); break;
	case PAR_FX_P2:          FxBus_setParameter(1, flt); break;
	case PAR_FX_P3:          FxBus_setParameter(2, flt); break;
	case PAR_FX_P4:          FxBus_setParameter(3, flt); break;
	case PAR_FX_RATIO:       Compressor_setRatio(&fxBus.compressor, value); break;
	case PAR_FX_WAVE:        Ringmod_setWave(&fxBus.ringmod, value); break;
	case PAR_FX_REVERB_TYPE: break;
	case PAR_FX_DELAY_TYPE:  fxBus.delay.delayType = value; break;
	default: break;
	}
}

//-----------------------------------------------------------
// this will check whether mtc is running, and if so will
// check to see whether we need to stop the sequencer due to
// lack of recent mtc activity. It will also reset our running indicator
// if the sequencer has stopped for some other reason
#if !EURORACK_MODULE
void midiParser_checkMtc()
{
	if(!midiParser_mtcIsRunning)
		return;

	if(!seq_isRunning()) {
		// inform mtc that his services are no longer needed
		midiParser_mtcIsRunning=0;
		return;
	}

	// at a 24fps framerate (the lowest) we should receive a completed message (we receive one every 2 frames)
	// every 83 ms. our tick counter is .25 ms resolution
	if(systick_ticks-midiParser_lastMtcReceived > 100 * 4) { // overestimate, just in case something untoward should happen
		// too much time has elapsed since our last message. mtc has gone away.
		midiParser_mtcIsRunning=0;

		uart_sendFrontpanelByte(FRONT_SEQ_CC);
		uart_sendFrontpanelByte(FRONT_SEQ_RUN_STOP);
		uart_sendFrontpanelByte(0);
		// stop the sequencer
		seq_setRunning(0);
	}
}
#endif
//------------------------------------------------------
// this fn assumes a valid voice is sent
// do_rec - whether we want to allow it to be recorded and echoed - we will only record
//          to the active track for notes received from the global channel
#if !EURORACK_MODULE
static void midiParser_noteOn(uint8_t voice, uint8_t note, uint8_t vel, uint8_t do_rec)
{

	if(menu_activePage == SEQ_PAGE)
	{
		//use incoming MIDI notes to set sequencer/step note
		const uint8_t step = activeParameters[PAR_ACTIVE_STEP];
		const uint8_t trackNr = menu_getActiveVoice(); //max 6 => 0x6 = 0b110
		const uint8_t patternNr = menu_getViewedPattern();


		seq_patternSet.seq_subStepPattern[patternNr][trackNr][step].note = note;
		activeParameters[PAR_STEP_NOTE] = note;
		menu_repaint();

	}
	else
	{

		if(seq_isTrackMuted(voice))
			return;

		// check the midi mode for the voice. If it's "any", trigger that note.
		// if it's some other note, trigger the drum voice only if it matches, and in this case
		// trigger the default note

		//if(midi_NoteOverride[voice] != 0) {
		if(activeParameters[PAR_MIDI_NOTE1 + voice] != 0) {
			// looking for specific note
			//if(note==midi_NoteOverride[voice])
			if(note==activeParameters[PAR_MIDI_NOTE1 + voice])
				note=SEQ_DEFAULT_NOTE; // match found. Play default note
			else
				return; // note does not match. Do nothing
		}

		voiceControl_noteOn(voice,note,vel);

		//Recording Mode - record the note to sequencer and echo to channel of that voice
		// (we'd want to hear what's being recorded)
		if(do_rec) {
			const uint8_t chan=midi_MidiChannels[voice];

			// record note if rec is on
			seq_addNote(voice,vel, note);

			//if a note is on for that channel send note-off first
			seq_midiNoteOff(chan);
			//send the new note to midi/usb out
			// todo a user played note will end up being turned off if a pattern switch happens.
			//           to fix this we'd have to differentiate between a user played note and a
			//           note triggered from sequencer, and also recognize note off on user played note and send it.
			seq_sendMidiNoteOn(chan, note, vel);
		}

	}

}
#endif
//------------------------------------------------------
//static void midiParser_noteOff(uint8_t voice, uint8_t note, uint8_t vel)
//{
	// in case we ever need it
//}


//-----------------------------------------------------------
/** Parse incoming midi messages and invoke corresponding action
 */
void midiParser_parseMidiMessage(MidiMsg msg)
{

#if !EURORACK_MODULE
	// route message if needed
	if(midiParser_routing.value) {
		if(msg.bits.source==midiSourceUSB) {
			if(midiParser_routing.route.usb2midi){
				// route to midi out port
				uart_sendMidi(msg);
			}
		} else if(msg.bits.source==midiSourceMIDI) {
			if(midiParser_routing.route.midi2midi) {
				// route to midi out port
				uart_sendMidi(msg);
			}
			if(midiParser_routing.route.midi2usb) {
				// route to usb out port
				usb_sendMidi(msg);
			}
		}
	}
#endif

	if(msg.bits.sysxbyte)
		return; // no further action needed. we don't interpret sysex data right now

	// FILT filter messages here. Filter inline below to be more optimal
	// we are interested in the low nibble since we are Rx here

#if !EURORACK_MODULE
	if((msg.status & 0xF0) == 0XF0) {
		// non-channel specific messages (system messages)
		switch(msg.status) {
		case MIDI_CLOCK:
			if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
				seq_sync();
			break;

		case MIDI_START:
			if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
			{
				sync_midiResetPosition();
				sync_midiStartStop(1);
			}
			break;
		case MIDI_CONTINUE:
			if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
				sync_midiStartStop(1);
			break;

		case MIDI_STOP:
			if((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) && seq_getExtSync())
				sync_midiStartStop(0);
			break;

		case MIDI_SONG_POSITION_POINTER:
			{
				/* Two data bytes follow the status. Just like with the Pitch Wheel,
				 * these two bytes are combined into a 14-bit value. (See Pitch Wheel).
				 * This 14-bit value is the MIDI Beat upon which to start the song.
				 * Songs are always assumed to start on a MIDI Beat of 0. Each MIDI
				 * Beat spans 6 MIDI Clocks. In other words, each MIDI Beat is a 16th
				 * note (since there are 24 MIDI Clocks in a quarter note).
				 *
				 */

				 const uint16_t spp = msg.data1 | (msg.data2<<7);
#pragma message"code the song position pointer stuff here!"
			}
			break;

		case MIDI_MTC_QFRAME:
			/* Strategy:
			 * If we get through all 8 of the mtc messages with a value of 0, it means that
			 * the song has just started playing. That is the only time we will start the
			 * sequencer. so we will not start it if they start the tape recorder playing half way
			 * through the song. Also, if the sequencer is running, or we are in external sync mode
			 * we will ignore mtc messages as well
			 */
			if ((midiParser_txRxFilter & MIDI_FILTER_SYSTEM) == 0)
				break; // ignore filtered

			// keep track of when we got the last mtc. only do this for the 0 msg to save time
			if((msg.data1 & 0x70)==0) {
				midiParser_lastMtcReceived=systick_ticks;
			}

			if(seq_isRunning()) {
				break; //already running, so we don't care to figure out where we are
			}
			if(seq_getExtSync())
				break; // bypass the lot. we are using external midi clock sync

			// figure out whether we are at 0:0:0:0
			if((msg.data1 & 0x7F)==0) { // this is the first mtc message of the set AND it's value is 0
				midiParser_mtcIgnore=0; // reset our level of ignorance
			} else if(midiParser_mtcIgnore) { // not the first msg and we are ignoring
				break; // get out of here fast
			} else if((msg.data1 & 0x70)!=0x70) { // messages 0 to 6 and we are not ignoring yet
				if((msg.data1 & 0x0F) !=0) {
					midiParser_mtcIgnore=1;
					break; // get out fast
				}
			} else { // message 7 and we are not ignoring yet
				if((msg.data1 & 0x01)==0) { // hour high nibble is 0
					// well, we got all the way thru all 8 messages with 0, so the song has just begun
					// tell the front that we've started running on our own
					uart_sendFrontpanelByte(FRONT_SEQ_CC);
					uart_sendFrontpanelByte(FRONT_SEQ_RUN_STOP);
					uart_sendFrontpanelByte(1);
					midiParser_mtcIgnore=1; // in case we happen to miss a 0 message. probably wouldn't happen, but...
					midiParser_mtcIsRunning=1;
					midiParser_lastMtcReceived=systick_ticks; // also might not be needed, but...
					// start the sequencer
					seq_setRunning(1);
				}
			}

			break;
		default:
			break;
		}

	} else
#endif
		{ // channel specific message
		const uint8_t msgonly =msg.status & 0xF0;
		const uint8_t chanonly=msg.status & 0x0F;
#if !EURORACK_MODULE
		if((msgonly & 0xE0) == 0x80) {
			// note on or note off message (one of these two only)
			if(midiParser_txRxFilter & MIDI_FILTER_NOTES) {
				int8_t v, q=-1;
				// if a note message comes in on global channel, then send that note to
				// the voice that is currently active on the front.
				if(midi_MidiChannels[7]==chanonly) {
					q=frontParser_activeTrack; // avoid sending it again later if the active track happens to have the same channel set
											   // (this might not really matter. does sending a note on twice do any harm?)
					if(msgonly==NOTE_ON && msg.data2) {
						midiParser_noteOn(frontParser_activeTrack, msg.data1, msg.data2, 1);
					} else { // NOTE_OFF or zero velocity note
						//midiParser_noteOff(v, msg.data1, msg.data2);
					}
				}

				// check each voice to see if it cares about this message
				for(v=0;v<7;v++) {
					if(midi_MidiChannels[v]==chanonly && v != q) { // if channel match and we haven't sent it already for the voice
						if(msgonly==NOTE_ON && msg.data2) {
							midiParser_noteOn(v, msg.data1, msg.data2, 1);
							//Also used in sequencer trigger note function
						} else { // NOTE_OFF or zero velocity note
							//midiParser_noteOff(v, msg.data1, msg.data2);
						}
					} // if channel matches
				} // for each voice
			} // check midi filter

		} else
#endif
			if(msgonly==PROG_CHANGE) {
			// respond to prog change and change patterns. This responds only when global channel matches the PC message's channel.
			if((midiParser_txRxFilter & MIDI_FILTER_PROG_C) && (chanonly == midi_MidiChannels[7]))
			{
				//seq_setNextPattern(msg.data1);
			}

		} else if(msgonly==MIDI_CC){
			// respond to CC message. This responds only when global channel matches the cc message's channel
			if((midiParser_txRxFilter & MIDI_FILTER_CC) && (chanonly == midi_MidiChannels[7])) {
				//record automation if record is turned on
#if !EURORACK_MODULE
				seq_recordAutomation(frontParser_activeTrack, msg.data1, msg.data2);
#endif

				//handle midi data
				midiParser_ccHandler(msg,1, 0, 0.f);
				//we received a midi cc message forward it to the front panel
				uart_sendFrontpanelByte(msg.status);
				uart_sendFrontpanelByte(msg.data1);
				uart_sendFrontpanelByte(msg.data2);
			}
		} else {
			// anything else
			// TODO MIDI_PITCH_WHEEL ?
		}
	} // channel specific vs non channel specific

}

//-----------------------------------------------------------

void midiParser_handleStatusByte(unsigned char data)
{
	// we received a channel voice/mode byte. set the status as appropriate
	switch(data&0xF0) {
	// 2 databyte messages
	case NOTE_OFF:
	case NOTE_ON:
	case MIDI_CC:
	case MIDI_PITCH_WHEEL:
	case MIDI_AT:
		midiMsg_tmp.status = data;	// store the new status byte
		parserState = MIDI_DATA1;	//status received, next should be data byte 1
		midiMsg_tmp.bits.length=2;// status is followed by 2 data bytes
		break;

	// 1 databyte messages
	case PROG_CHANGE:
	case CHANNEL_PRESSURE:
		midiMsg_tmp.status = data;	// store the new status byte
		parserState = MIDI_DATA1;	//status received, next should be data byte 1
		midiMsg_tmp.bits.length=1;// status is followed by 1 data bytes
		break;

	// messages we don't care about right now, and don't know how to handle or passthru (Are there any?).
	default:
		parserState = IGNORE;	// throw away any data bytes until next message
		midiMsg_tmp.bits.length=0;

		break;
	}
}
//-----------------------------------------------------------
#if !EURORACK_MODULE
// This will build up the midi message and hand it off to
// parseMidiMessage when it's complete
void midiParser_parseUartData(unsigned char data)
{

	if(data&0x80) { // High bit is set -  its either a status or a system message.
		// regardless of current state, we blindly start a new message without questioning it
		midiMsg_tmp.bits.sysxbyte=0;
		if( (data&0xf0) == 0xf0) { // system message
			midiMsg_tmp.status = data;
			switch(data) {
			case SYSEX_START: // get into sysex receive mode. any more bytes received until this status changes are considered
							  // to be sysex data. we still need to parse this sysex start, in case we are routing it
				parserState = SYSEX_DATA;
				midiMsg_tmp.bits.length=0;
				goto parseMsg; // we will still parse it in case we are doing a passthru
			case SYSEX_END:	  // get out of sysex mode
				if(parserState==SYSEX_DATA) {
					parserState=MIDI_STATUS;
					midiMsg_tmp.bits.length=0;
					goto parseMsg; // we will still parse it in case we are doing a passthru
				} else {
					// spurious sysex end msg received. ignore it
				}
				break; //
			// 1 byte payload messages
			case MIDI_SONG_SEL:		// passthru only
			case MIDI_MTC_QFRAME: 	// mtc chunk
				parserState = MIDI_DATA1; 	// we expect the nugget of mtc frame info
				midiMsg_tmp.bits.length=1;// we expect 1 data byte
				break;

			case MIDI_SONG_POSITION_POINTER:
				parserState = MIDI_DATA1; 	// we expect 14-bit value for song position
				midiMsg_tmp.bits.length=2;// we expect 1 data byte
				break;

			// 0 byte payload messages (we will assume that any system message
			// other than those above has 0 byte payload)
			default:
				midiMsg_tmp.bits.length=0;
				goto parseMsg;
			}
		} else { //status byte (channel specific message containing a channel number)
			midiParser_handleStatusByte(data);
		}
	} else { // high bit is not set - it's a data byte

		switch(parserState)	{
		case MIDI_STATUS: // we are expecting status msg, but got data, so running status may be in effect
			if(midiMsg_tmp.bits.length) {
				midiMsg_tmp.data1 = data;
				if(midiMsg_tmp.bits.length==2)
					parserState=MIDI_DATA2;
				else {
					midiMsg_tmp.data2=0;
					goto parseMsg;
				}
			} else {
				break; // last msg had 0 payload, so wtf is this? just ignore it
			}
			break;

		case MIDI_DATA1:
			midiMsg_tmp.data1 = data;
			if(midiMsg_tmp.bits.length==2) {
				// we need another byte before we can do anything meaningful
				parserState = MIDI_DATA2;
			} else { // it must be 1
				goto parseMsg;
			}
			break;
		case MIDI_DATA2:
			midiMsg_tmp.data2 = data;
			goto parseMsg; // message complete
		case SYSEX_DATA: // we are in sysex mode
			midiMsg_tmp.bits.sysxbyte=1;
			midiMsg_tmp.status = data; // status will contain the sysex byte
			midiMsg_tmp.bits.length=0;
			goto parseMsg;
		default: //we are expecting no data byte, but we got one.
			// ignore it
			break;
		} // switch parserState
	} // if high bit is set

	return;

parseMsg:
	// we get here if we have proudly received a message that we want to do something with
	if(parserState != SYSEX_DATA) // we are still in sysex receive mode
		parserState = MIDI_STATUS; // next byte should be a new message, or we don't care about it
	midiMsg_tmp.bits.source=midiSourceMIDI;
	midiParser_parseMidiMessage(midiMsg_tmp);

}
#endif
// 0 - Off - nothing to nothing
// 1 - U2M - usb in to midi out
// 2 - M2M - midi in to midi out
// 3 - A2M - usb in and midi in to midi out
// 4 - M2U - midi in to usb out
// 5 - M2A - midi in to usb out and midi out

void midiParser_setRouting(uint8_t value)
{
	midiParser_routing.value=0;

	switch(value) {
	case 1:
		midiParser_routing.route.usb2midi=1;
		break;
	case 2:
		midiParser_routing.route.midi2midi=1;
		break;
	case 3:
		midiParser_routing.route.usb2midi=1;
		midiParser_routing.route.midi2midi=1;
		break;
	case 4:
		midiParser_routing.route.midi2usb=1;
		break;
	case 5:
		midiParser_routing.route.midi2midi=1;
		midiParser_routing.route.midi2usb=1;
		break;
	default:
	case 0:

		break;
	}

}

void midiParser_setFilter(uint8_t is_tx, uint8_t value)
{

	if(is_tx) // set the high nibble to value
		midiParser_txRxFilter = (value << 4) | (midiParser_txRxFilter & 0x0F);
	else // set the low nibble to value
		midiParser_txRxFilter = (value & 0x0F) | (midiParser_txRxFilter & 0xF0);

}
