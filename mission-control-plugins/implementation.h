/* Mission Control plugin API - internals, for MC to use
 *
 * Copyright (C) 2009 Nokia Corporation
 * Copyright (C) 2009 Collabora Ltd.
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

#ifndef MCP_IMPLEMENTATION_H
#define MCP_IMPLEMENTATION_H

#include <mission-control-plugins/mission-control-plugins.h>

G_BEGIN_DECLS

struct _McpRequestIface {
    GTypeInterface parent;

    /* Account */
    const gchar * (*get_account_path) (McpRequest *self);
    const gchar * (*get_protocol) (McpRequest *self);
    const gchar * (*get_cm_name) (McpRequest *self);

    gint64 (*get_user_action_time) (McpRequest *self);
    guint (*get_n_requests) (McpRequest *self);
    GHashTable * (*ref_nth_request) (McpRequest *self, guint n);

    void (*deny) (McpRequest *self, GQuark domain, gint code,
        const gchar *message);
};

struct _McpDispatchOperationIface {
    GTypeInterface parent;

    /* Account and Connection */
    const gchar * (*get_account_path) (McpDispatchOperation *self);
    const gchar * (*get_connection_path) (McpDispatchOperation *self);
    const gchar * (*get_protocol) (McpDispatchOperation *self);
    const gchar * (*get_cm_name) (McpDispatchOperation *self);

    /* Channels */
    guint (*get_n_channels) (McpDispatchOperation *self);
    const gchar * (*get_nth_channel_path) (McpDispatchOperation *self,
        guint n);
    GHashTable * (*ref_nth_channel_properties) (McpDispatchOperation *self,
        guint n);

    /* Delay the dispatch */
    McpDispatchOperationDelay * (*start_delay) (McpDispatchOperation *self);
    void (*end_delay) (McpDispatchOperation *self,
        McpDispatchOperationDelay *delay);

    /* Close */
    void (*leave_channels) (McpDispatchOperation *self,
        gboolean wait_for_observers, TpChannelGroupChangeReason reason,
        const gchar *message);
    void (*close_channels) (McpDispatchOperation *self,
        gboolean wait_for_observers);
    void (*destroy_channels) (McpDispatchOperation *self,
        gboolean wait_for_observers);
};

struct _McpAccountIface {
  GTypeInterface parent;

  void (*set_value) (const McpAccount *ma,
      const gchar *acct,
      const gchar *key,
      const gchar *value);

  gchar * (*get_value) (const McpAccount *ma,
      const gchar *acct,
      const gchar *key);

  gboolean (*is_secret) (const McpAccount *ma,
      const gchar *acct,
      const gchar *key);

  void (* make_secret) (const McpAccount *ma,
      const gchar *acct,
      const gchar *key);
};

G_END_DECLS

#endif
