from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import query
from django.db import models
from datetime import datetime
import logging
from softdelete.signals import pre_soft_delete, pre_undelete, \
     post_soft_delete, post_undelete


class SoftDeleteQuerySet(query.QuerySet):
    def all_with_deleted(self):
        qs = super(SoftDeleteQuerySet, self).all()
        qs.__class__ = SoftDeleteQuerySet
        return qs
    
    def soft_delete(self, using='default', do_related=True, *args, **kwargs):
        if not len(self):
            return
        logging.debug("STARTING QUERYSET SOFT-DELETE: %s. %s" % (self, len(self)))
        for obj in self:
            logging.debug(" -----  CALLING soft_delete() on %s" % obj)
            obj.soft_delete(using=using, do_related=do_related, *args, **kwargs)

    def undelete(self, using='default', do_related=True, *args, **kwargs):
        logging.debug("UNDELETING %s" % self)
        for obj in self:
            obj.undelete(using=using, do_related=do_related, *args, **kwargs)
        logging.debug("FINISHED UNDELETING %s" %self)


class SoftDeleteManager(models.Manager):
    def get_query_set(self):
        qs = super(SoftDeleteManager,self).get_query_set().filter(deleted_at__isnull=1)
        qs.__class__ = SoftDeleteQuerySet
        return qs

    def all_with_deleted(self, prt=False):
        if hasattr(self, 'core_filters'): # it's a RelatedManager
            qs = super(SoftDeleteManager, self).get_query_set().filter(**self.core_filters)
        else:
            qs = super(SoftDeleteManager, self).get_query_set()
        qs.__class__ = SoftDeleteQuerySet
        return qs

    def soft_deleted_set(self):
        qs = super(SoftDeleteManager, self).get_query_set().filter(deleted_at__isnull=0)
        qs.__class__ = SoftDeleteQuerySet
        return qs

    def get(self, *args, **kwargs):
        return self.all_with_deleted().get(*args, **kwargs)

    def filter(self, *args, **kwargs):
        if 'pk' in kwargs:
            qs = self.all_with_deleted().filter(*args, **kwargs)
        else:
            qs = self.get_query_set().filter(*args, **kwargs)
        qs.__class__ = SoftDeleteQuerySet
        return qs


class SoftDeleteObject(models.Model):
    deleted_at = models.DateTimeField(blank=True, null=True, default=None,
                                      editable=False)
    objects = SoftDeleteManager()

    class Meta:
        abstract = True
        
    def __init__(self, *args, **kwargs):
        super(SoftDeleteObject, self).__init__(*args, **kwargs)
        self.__dirty = False

    def get_deleted(self):
        return self.deleted_at != None

    def set_deleted(self, d):
        """Called via the admin interface (if user checks the
        "deleted" checkox).
        """
        self.__dirty = True 
        if d and not self.deleted_at:
            self.deleted_at = datetime.utcnow()
        elif not d and self.deleted_at:
            self.deleted_at = None

    deleted = property(get_deleted, set_deleted)

    def _do_soft_delete(self, related, using, do_related):
        rel = related.get_accessor_name()
        try:
            getattr(self, rel).all().soft_delete(using=using, do_related=do_related)
        except AttributeError, ObjectDoesNotExist:
            # getattr(self, rel).__class__.objects.all().soft_delete()
            pass

    def soft_delete(self, *args, **kwargs):
        using = kwargs.get('using', settings.DATABASES['default'])
        do_related = kwargs.pop('do_related', True)
        pre_soft_delete.send(sender=self.__class__,
                             instance=self,
                             using=using)
        logging.debug('SOFT DELETING type: %s, %s' % (type(self), self))
        self.deleted_at = datetime.today()
        self.save()
        if do_related:
            for related in self._meta.get_all_related_objects():
                self._do_soft_delete(related, using, do_related)
        logging.debug("FINISHED SOFT DELETING RELATED %s" % self)
        post_soft_delete.send(sender=self.__class__,
                              instance=self,
                              using=using)

    def _do_undelete(self, related, using, do_related):
        rel = related.get_accessor_name()
        try:
            getattr(self, rel).soft_deleted_set().undelete(using=using, do_related=do_related)
        except AttributeError:
            # getattr(self, rel).__class__.objects.all().soft_delete()
            pass

    def undelete(self, *args, **kwargs):
        logging.debug('UNDELETING %s' % self)
        using = kwargs.get('using', settings.DATABASES['default'])
        do_related = kwargs.pop('do_related', True)
        pre_undelete.send(sender=self.__class__,
                          instance=self,
                          using=using)
        self.deleted_at = None
        self.save()
        if do_related:
            for related in self._meta.get_all_related_objects():
                try:
                    self._do_undelete(related, using, do_related)
                except AttributeError:
                    raise
        post_undelete.send(sender=self.__class__,
                           instance=self,
                           using=using)
        logging.debug('FINISHED UNDELETING RELATED %s' % self)

    def save(self, **kwargs):
        super(SoftDeleteObject, self).save(**kwargs)
        if self.__dirty:
            self.__dirty = False
            if not self.deleted:
                self.undelete()
            else:
                self.soft_delete()
