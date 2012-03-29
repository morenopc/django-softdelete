from django.db.models import loading
from django.core.management import call_command
from django.conf import settings
from softdelete.tests.test_sd import *

settings.INSTALLED_APPS.append('softdelete.test_softdelete_app')
loading.cache.loaded = False
call_command('syncdb', interactive=False, verbosity=False)
