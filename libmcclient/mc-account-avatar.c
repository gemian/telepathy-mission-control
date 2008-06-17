/*
 * mc-account-avatar.c - Telepathy Account D-Bus interface (client side)
 *
 * Copyright (C) 2008 Nokia Corporation
 *
 * Contact: Alberto Mardegan  <alberto.mardegan@nokia.com>
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 */

#include <stdio.h>
#include <string.h>
#include "mc-account.h"
#include "mc-account-priv.h"
#include "dbus-api.h"
#include "mc-signals-marshal.h"

struct _McAccountAvatarProps {
    GArray *avatar;
    gchar *mime_type;
};


void
_mc_account_avatar_props_free (McAccountAvatarProps *props)
{
    g_free (props->mime_type);
    if (props->avatar)
	g_array_free (props->avatar, TRUE);
    g_free (props);
}

void
_mc_account_avatar_class_init (McAccountClass *klass)
{
    _mc_account_signals[AVATAR_CHANGED] =
	g_signal_new ("avatar-changed",
		      G_OBJECT_CLASS_TYPE (klass),
		      G_SIGNAL_RUN_LAST | G_SIGNAL_DETAILED,
		      0,
		      NULL, NULL,
		      mc_signals_marshal_VOID__BOXED_STRING,
		      G_TYPE_NONE,
		      2, dbus_g_type_get_collection ("GArray", G_TYPE_UCHAR),
		      G_TYPE_STRING);
}

static void
set_avatar (McAccount *account, const GValue *value, gboolean emit_changed)
{
    McAccountAvatarProps *props = account->priv->avatar_props;
    GValueArray *va;

    g_free (props->mime_type);
    if (props->avatar)
	g_array_free (props->avatar, TRUE);
    va = g_value_get_boxed (value);
    props->avatar = g_value_get_boxed (va->values);
    _mc_gvalue_stolen (va->values);
    props->mime_type = g_value_dup_string (va->values + 1);
    if (emit_changed)
    {
	g_signal_emit (account, _mc_account_signals[AVATAR_CHANGED], 0,
		       props->avatar, props->mime_type);
    }
}

static void
update_property (gpointer key, gpointer ht_value, gpointer user_data)
{
    McAccount *account = user_data;
    GValue *value = ht_value;
    const gchar *name = key;

    if (strcmp (name, "Avatar") == 0)
    {
	set_avatar (account, value, FALSE);
    }
}

static void
create_props (TpProxy *proxy, GHashTable *props)
{
    McAccount *account = MC_ACCOUNT (proxy);
    McAccountPrivate *priv = account->priv;

    priv->avatar_props = g_malloc0 (sizeof (McAccountAvatarProps));
    g_hash_table_foreach (props, update_property, account);
}

static void
get_avatar_cb (TpProxy *proxy, const GValue *v_avatar,
	       const GError *error, gpointer user_data,
	       GObject *weak_object)
{
    McAccount *account = MC_ACCOUNT (proxy);

    if (error)
    {
	g_warning ("%s: got error: %s", G_STRFUNC, error->message);
	return;
    }

    if (account->priv->avatar_props)
	set_avatar (account, v_avatar, TRUE);
}

static void
on_avatar_changed (TpProxy *proxy, gpointer user_data, GObject *weak_object)
{
    /* the avatar is not passed along with the parameters, we must retrieve it
     */
    tp_cli_dbus_properties_call_get (proxy, -1,
				     MC_IFACE_ACCOUNT_INTERFACE_AVATAR,
				     "Avatar",
				     get_avatar_cb, NULL, NULL, NULL);
}

void
mc_account_avatar_call_when_ready (McAccount *account, McAccountWhenReadyCb callback,
				   gpointer user_data)
{
    McIfaceData iface_data;

    iface_data.id = MC_IFACE_QUARK_ACCOUNT_INTERFACE_AVATAR;
    iface_data.props_data_ptr = (gpointer *)&account->priv->avatar_props;
    iface_data.create_props = create_props;

    if (_mc_iface_call_when_ready_int ((TpProxy *)account,
				       (McIfaceWhenReadyCb)callback, user_data,
				       &iface_data))
    {
	mc_cli_account_interface_avatar_connect_to_avatar_changed (account,
								   on_avatar_changed,
								   NULL, NULL,
								   NULL, NULL);
    }
}

void
mc_account_avatar_get (McAccount *account,
		       const gchar **avatar, gsize *length,
		       const gchar **mime_type)
{
    McAccountAvatarProps *props;

    g_return_if_fail (MC_IS_ACCOUNT (account));
    props = account->priv->avatar_props;
    if (G_UNLIKELY (!props))
    {
	*avatar = NULL;
	*length = 0;
	*mime_type = NULL;
	return;
    }

    *avatar = props->avatar->data;
    *length = props->avatar->len;
    *mime_type = props->mime_type;
}
