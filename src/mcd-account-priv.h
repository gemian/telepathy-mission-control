/*
 * This file is part of mission-control
 *
 * Copyright (C) 2007 Nokia Corporation. 
 *
 * Contact: Naba Kumar  <naba.kumar@nokia.com>
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * version 2.1 as published by the Free Software Foundation.
 *
 * This library is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
 * 02110-1301 USA
 *
 */

#ifndef __MCD_ACCOUNT_PRIV_H__
#define __MCD_ACCOUNT_PRIV_H__

#include "mcd-account-config.h"

enum
{
    CONNECTION_STATUS_CHANGED,
    CURRENT_PRESENCE_CHANGED,
    REQUESTED_PRESENCE_CHANGED,
    VALIDITY_CHANGED,
    AVATAR_CHANGED,
    ALIAS_CHANGED,
    CONNECTION_PROCESS,
    LAST_SIGNAL
};

extern guint _mcd_account_signals[LAST_SIGNAL];

void _mcd_account_connect (McdAccount *account, GHashTable *params);

#endif /* __MCD_ACCOUNT_PRIV_H__ */

