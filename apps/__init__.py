# Package marker for the apps directory.
#
# Apps live in the ``apps`` namespace and are referenced as ``apps.<name>``
# (INSTALLED_APPS, urls, imports) — e.g. ``apps.students``. ``config/settings.py``
# therefore no longer inserts ``apps/`` into sys.path. Models/migrations keep the
# short app labels (``students``, ``tenants``, ...) via each ``apps.py``'s
# ``label`` attribute.