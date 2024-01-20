from sqlalchemy import Column, DateTime, func

from db.base import Session

DEFAULT_TIMEZONE = 'UTC'


def get_or_create(session: Session, model, defaults=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance, False
    else:
        kwargs.update(defaults or {})
        instance = model(**kwargs)
        session.add(instance)
        session.flush()
        return instance, True


def db_created(**kw):
    if 'nullable' not in kw:
        kw['nullable'] = False
    if 'default' not in kw:
        kw['default'] = func.timezone(DEFAULT_TIMEZONE, func.current_timestamp())
    if 'index' not in kw:
        kw['index'] = True
    if 'doc' not in kw:
        kw['doc'] = u'Created Date'
    return Column(DateTime, **kw)


def db_updated(**kw):
    if 'nullable' not in kw:
        kw['nullable'] = False
    if 'default' not in kw:
        kw['default'] = func.timezone(DEFAULT_TIMEZONE, func.current_timestamp())
    if 'onupdate' not in kw:
        kw['onupdate'] = func.timezone(DEFAULT_TIMEZONE, func.current_timestamp())
    if 'doc' not in kw:
        kw['doc'] = u'Updated Date'
    return Column(DateTime, **kw)
