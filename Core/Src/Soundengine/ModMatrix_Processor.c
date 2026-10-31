/*
 * CV_Processor.c
 *
 *  Created on: Apr 20, 2022
 *      Author: julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include <Soundengine/ModMatrix_Processor.h>
#include "Shard/sh_bridge.h"

/* SHARD: the CV matrix now modulates the channel parameters directly, see
 * sh_cvProcess() in Shard/sh_bridge.c. */

void CV_Init()
{
}

void CV_process()
{
	sh_cvProcess();
}

float CV_getBpm()
{
	return 0.f;
}
