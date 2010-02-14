/*
 * A demonstration plugin that diverts account storage to an alternate location.
 *
 * Copyright © 2010 Nokia Corporation
 * Copyright © 2010 Collabora Ltd.
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

#include <mission-control-plugins/mission-control-plugins.h>

#define DIVERTED_CFG "/tmp/mcp-test-diverted-account-plugin.conf"

#define PLUGIN_NAME  "diverted-keyfile"
#define PLUGIN_PRIORITY (ACCOUNT_STORAGE_PLUGIN_PRIO_DEFAULT + 100)
#define PLUGIN_DESCRIPTION \
  "Test plugin that grabs all accounts it receives and diverts them to '" \
  DIVERTED_CFG "' instead of the usual location"

#define DEBUG g_debug

typedef struct {
  GObject parent;
  GKeyFile *keyfile;
  gboolean save;
  gboolean loaded;
} AccountDiversionPlugin;

typedef struct {
  GObjectClass parent_class;
} AccountDiversionPluginClass;

GType account_diversion_plugin_get_type (void) G_GNUC_CONST;
static void account_storage_iface_init (McpAccountStorageIface *,
    gpointer);


#define ACCOUNT_DIVERSION_PLUGIN(o) \
  (G_TYPE_CHECK_INSTANCE_CAST ((o), account_diversion_plugin_get_type (), \
      AccountDiversionPlugin))

G_DEFINE_TYPE_WITH_CODE (AccountDiversionPlugin, account_diversion_plugin,
    G_TYPE_OBJECT,
    G_IMPLEMENT_INTERFACE (MCP_TYPE_ACCOUNT_STORAGE,
        account_storage_iface_init));

static void
account_diversion_plugin_init (AccountDiversionPlugin *self)
{
  DEBUG ("account_diversion_plugin_init");
  self->keyfile = g_key_file_new ();
  self->save = FALSE;
  self->loaded = FALSE;
}

static void
account_diversion_plugin_class_init (AccountDiversionPluginClass *cls)
{
  DEBUG ("account_diversion_plugin_class_init");
  storage = g_key_file_new ();
}

static gboolean
_have_config (void)
{
  DEBUG ("checking for " DIVERTED_CFG);
  return g_file_test (DIVERTED_CFG, G_FILE_TEST_EXISTS);
}

static void
_create_config (void)
{
  gchar *dir = g_path_get_dirname (DIVERTED_CFG);
  g_mkdir_with_parents (dir, 0700);
  g_free (dir);
  g_file_set_contents (DIVERTED_CFG, "# diverted accounts\n", -1, NULL);
  DEBUG ("created " DIVERTED_CFG);
}

static gboolean
_set (const McpAccountStorage *self,
    const McpAccount *am,
    const gchar *acct,
    const gchar *key,
    const gchar *val)
{
  AccountDiversionPlugin *adp = ACCOUNT_DIVERSION_PLUGIN (self);

  adp->save = TRUE;
  g_key_file_set_string (adp->keyfile, acct, key, val);

  return TRUE;
}

static gboolean
_get (const McpAccountStorage *self,
    const McpAccount *am,
    const gchar *acct,
    const gchar *key)
{
  AccountDiversionPlugin *adp = ACCOUNT_DIVERSION_PLUGIN (self);

  if (key != NULL)
    {
      gchar *v = g_key_file_get_string (adp->keyfile, acct, key, NULL);

      if (v == NULL)
        return FALSE;

      mcp_account_set_value (am, acct, key, v);
      g_free (v);
    }
  else
    {
      gsize i;
      gsize n;
      GStrv keys = g_key_file_get_keys (adp->keyfile, acct, &n, NULL);

      for (i = 0; i < n; i++)
        {
          gchar *v = g_key_file_get_string (adp->keyfile, acct, keys[i], NULL);
          if (v != NULL)
            mcp_account_set_value (am, acct, keys[i], v);
          g_free (v);
        }

      g_strfreev (keys);
    }

  return TRUE;
}

static gboolean
_delete (const McpAccountStorage *self,
      const McpAccount *am,
      const gchar *acct,
      const gchar *key)
{
  AccountDiversionPlugin *adp = ACCOUNT_DIVERSION_PLUGIN (self);

  if (key == NULL)
    {
      if (g_key_file_remove_group (adp->keyfile, acct, NULL))
        adp->save = TRUE;
    }
  else
    {
      gsize n;
      GStrv keys;
      if (g_key_file_remove_key (adp->keyfile, acct, key, NULL))
        adp->save = TRUE;
      keys = g_key_file_get_keys (adp->keyfile, acct, &n, NULL);
      if (keys == NULL || n == 0)
        g_key_file_remove_group (adp->keyfile, acct, NULL);
      g_strfreev (keys);
    }

  return TRUE;
}


static gboolean
_commit (const McpAccountStorage *self,
    const McpAccount *am)
{
  gsize n;
  gchar *data;
  AccountDiversionPlugin *adp = ACCOUNT_DIVERSION_PLUGIN (self);
  gboolean rval = FALSE;

  if (!adp->save)
    return TRUE;

  if (!_have_config ())
    _create_config ();

  data = g_key_file_to_data (adp->keyfile, &n, NULL);
  rval = g_file_set_contents (DIVERTED_CFG, data, n, NULL);
  adp->save = !rval;
  g_free (data);

  return rval;
}

static GList *
_list (const McpAccountStorage *self,
    const McpAccount *am)
{
  gsize i;
  gsize n;
  GStrv accounts;
  GList *rval = NULL;
  AccountDiversionPlugin *adp = ACCOUNT_DIVERSION_PLUGIN (self);

  if (!_have_config ())
    _create_config ();

  if (!adp->loaded)
    adp->loaded = g_key_file_load_from_file (adp->keyfile, DIVERTED_CFG,
        G_KEY_FILE_KEEP_COMMENTS, NULL);

  accounts = g_key_file_get_groups (adp->keyfile, &n);
  for (i = 0; i < n; i++)
    rval = g_list_prepend (rval, g_strdup (accounts[i]));
  g_strfreev (accounts);

  return rval;
}

static void
account_storage_iface_init (McpAccountStorageIface *iface,
    gpointer unused G_GNUC_UNUSED)
{
  mcp_account_storage_iface_set_name (iface, PLUGIN_NAME);
  mcp_account_storage_iface_set_desc (iface, PLUGIN_DESCRIPTION);
  mcp_account_storage_iface_set_priority (iface, PLUGIN_PRIORITY);

  mcp_account_storage_iface_implement_get (iface, _get);
  mcp_account_storage_iface_implement_set (iface, _set);
  mcp_account_storage_iface_implement_delete (iface, _delete);
  mcp_account_storage_iface_implement_commit (iface, _commit);
  mcp_account_storage_iface_implement_list (iface, _list);
}


GObject *
mcp_plugin_ref_nth_object (guint n)
{
  DEBUG ("Initializing mcp-account-diversion-plugin (n=%u)", n);

  switch (n)
    {
    case 0:
      return g_object_new (account_diversion_plugin_get_type (), NULL);

    default:
      return NULL;
    }
}
