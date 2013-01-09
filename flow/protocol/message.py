import copy
import json
from flow.protocol import exceptions


class Message(object):
    required_fields = {}
    optional_fields = {}

    def __init__(self, **kwargs):
        try:
            for name, type_ in self.required_fields.iteritems():
                value = kwargs.pop(name)
                if isinstance(value, type_):
                    setattr(self, name, value)
                else:
                    raise exceptions.InvalidMessageException(
                            'Message (%s) requires %s have type (%s)' %
                            (self.__class__.__name__, name, type_))

        except KeyError:
            raise exceptions.InvalidMessageException(
                    'Required field %s is missing' % name)

        for name, type_ in self.optional_fields.iteritems():
            value = kwargs.pop(name, None)
            if value is not None:
                if isinstance(value, type_):
                    setattr(self, name, value)
                else:
                    raise exceptions.InvalidMessageException(
                            'Message (%s) requires %s have type (%s)' %
                            (self.__class__.__name__, name, type_))

        if kwargs:
            raise exceptions.InvalidMessageException(
                    'Additional arguments passed to constructor for %s: %s' %
                    (self.__class__.__name__, kwargs))

        self.validate()


    def validate(self):
        pass

    def to_dict(self):
        data = copy.copy(self.__dict__)
        data['message_class'] = self.__class__.__name__
        return data

    def __eq__(self, other):
        return self.to_dict() == other.to_dict()
